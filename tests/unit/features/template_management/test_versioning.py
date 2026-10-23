"""Unit tests for template version history."""

import pytest
from click.testing import CliRunner
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from reportmaker.features.report_generation.models import ReportConfig
from reportmaker.features.template_management.exceptions import (
    TemplateNotFoundError,
    TemplateVersionNotFoundError,
)
from reportmaker.features.template_management.models import VersionSource
from reportmaker.features.template_management.services import TemplateManager
from reportmaker.features.template_management import versioning
from reportmaker.features.template_management.versioning import VersionStore
from reportmaker.main import cli


def make_config(query: str = "SELECT 1", name: str = "Sales") -> ReportConfig:
    return ReportConfig(
        name=name, data_source={"url": "sqlite:///demo.db", "query": query}
    )


class TestCapture:
    def test_first_save_has_no_history(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config())
        assert manager.list_versions("sales") == []

    def test_forced_save_snapshots_what_it_replaces(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(make_config("SELECT 1"))
        before = path.read_bytes()
        manager.save_config(make_config("SELECT 2"), force=True)

        (version,) = manager.list_versions("sales")
        assert version.source is VersionSource.SAVE
        assert manager.rollback("sales", version.version_id).read_bytes() == before

    def test_delete_keeps_history_and_rollback_recreates(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(make_config())
        before = path.read_bytes()
        manager.delete_template("sales")

        (version,) = manager.list_versions("sales")
        assert version.source is VersionSource.DELETE
        manager.rollback("sales", version.version_id)
        assert path.read_bytes() == before

    def test_forced_import_snapshots_what_it_replaces(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        blank = manager.create_blank_xlsx(str(tmp_path / "blank.xlsx"))
        assert manager.import_from_xlsx(str(blank)).success
        name = manager.list_templates()[0].name
        manager.import_from_xlsx(str(blank), force=True)

        (version,) = manager.list_versions(name)
        assert version.source is VersionSource.IMPORT

    def test_history_directory_is_not_listed_as_a_template(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config("SELECT 1"))
        manager.save_config(make_config("SELECT 2"), force=True)
        assert [i.name for i in manager.list_templates()] == ["sales"]

    def test_identical_content_is_not_recorded_twice(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config("SELECT 1"))
        for _ in range(3):
            manager.save_config(make_config("SELECT 1"), force=True)
        assert len(manager.list_versions("sales")) == 1


class TestRollbackAndDiff:
    def test_rollback_is_itself_undoable(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(make_config("SELECT 1"))
        manager.save_config(make_config("SELECT 2"), force=True)
        newest = path.read_bytes()
        oldest = manager.list_versions("sales")[0].version_id

        manager.rollback("sales", oldest)
        assert path.read_bytes() != newest
        undo = manager.list_versions("sales")[0]
        assert undo.source is VersionSource.ROLLBACK
        manager.rollback("sales", undo.version_id)
        assert path.read_bytes() == newest

    def test_diff_against_current_shows_the_change(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config("SELECT 1"))
        manager.save_config(make_config("SELECT 2"), force=True)
        version = manager.list_versions("sales")[0].version_id

        diff = manager.diff_versions("sales", version)
        assert "-  query: SELECT 1" in diff
        assert "+  query: SELECT 2" in diff

    def test_diff_of_identical_content_is_empty(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config("SELECT 1"))
        manager.save_config(make_config("SELECT 2"), force=True)
        version = manager.list_versions("sales")[0].version_id
        manager.rollback("sales", version)
        assert manager.diff_versions("sales", version) == ""

    def test_diff_between_two_versions(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        for query in ("SELECT 1", "SELECT 2", "SELECT 3"):
            manager.save_config(make_config(query), force=True)
        newer, older = (v.version_id for v in manager.list_versions("sales"))
        assert "+  query: SELECT 2" in manager.diff_versions("sales", older, newer)

    def test_unknown_version_is_reported(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config())
        with pytest.raises(TemplateVersionNotFoundError):
            manager.rollback("sales", "20260101T000000000000Z__save")

    @pytest.mark.parametrize(
        "version_id", ["../../etc/passwd", "..", "", "20260101T000000000000Z__save/x"]
    )
    def test_version_ids_cannot_escape_the_history_folder(self, tmp_path, version_id):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config())
        with pytest.raises(TemplateVersionNotFoundError):
            manager.diff_versions("sales", version_id)

    def test_diff_with_missing_current_file_is_reported(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        manager.save_config(make_config())
        manager.delete_template("sales")
        version = manager.list_versions("sales")[0].version_id
        with pytest.raises(TemplateNotFoundError):
            manager.diff_versions("sales", version)


class TestRetention:
    def test_keeps_only_the_newest_versions(self, tmp_path):
        manager = TemplateManager(str(tmp_path), max_versions=3)
        for n in range(8):
            manager.save_config(make_config(f"SELECT {n}"), force=True)
        versions = manager.list_versions("sales")
        assert len(versions) == 3
        # SELECT 7 is current, so the newest snapshot holds SELECT 6.
        assert "SELECT 6" in manager.diff_versions("sales", versions[0].version_id)

    def test_default_limit_is_fifty(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        for n in range(55):
            manager.save_config(make_config(f"SELECT {n}"), force=True)
        assert len(manager.list_versions("sales")) == 50

    def test_rejects_a_limit_below_one(self, tmp_path):
        with pytest.raises(ValueError):
            VersionStore(tmp_path, max_versions=0)

    def test_ids_stay_ordered_when_edits_land_in_the_same_microsecond(
        self, tmp_path, monkeypatch
    ):
        from datetime import datetime, timezone

        frozen = datetime(2026, 1, 1, tzinfo=timezone.utc)

        class FrozenClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return frozen

        monkeypatch.setattr(versioning, "datetime", FrozenClock)
        store = VersionStore(tmp_path)
        for n in range(4):
            store.snapshot("t", f"v{n}".encode(), VersionSource.SAVE)
        ids = [v.version_id for v in store.list_versions("t")]
        assert ids == sorted(ids, reverse=True)
        assert len(set(ids)) == 4


class TestProperties:
    @settings(
        max_examples=60,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        queries=st.lists(
            st.text(alphabet="abcdefgh 0123456789", min_size=1, max_size=12),
            min_size=2,
            max_size=8,
        ),
        data=st.data(),
    )
    def test_rollback_restores_any_recorded_version_exactly(
        self, tmp_path_factory, queries, data
    ):
        manager = TemplateManager(str(tmp_path_factory.mktemp("t")))
        path = manager.save_config(make_config("SELECT 'start'"))
        recorded = {}
        for query in queries:
            before = path.read_bytes()
            manager.save_config(make_config(f"SELECT '{query}'"), force=True)
            if path.read_bytes() != before:
                recorded[manager.list_versions("sales")[0].version_id] = before

        if not recorded:
            return
        version_id = data.draw(st.sampled_from(sorted(recorded)))
        manager.rollback("sales", version_id)
        assert path.read_bytes() == recorded[version_id]


class TestCli:
    def test_history_diff_and_rollback_round_trip(self, tmp_path):
        manager = TemplateManager(str(tmp_path))
        path = manager.save_config(make_config("SELECT 1"))
        original = path.read_bytes()
        manager.save_config(make_config("SELECT 2"), force=True)
        version = manager.list_versions("sales")[0].version_id
        runner = CliRunner()
        base = ["--templates-dir", str(tmp_path)]

        history = runner.invoke(cli, ["template", "history", "sales", *base])
        assert history.exit_code == 0 and version in history.output

        diff = runner.invoke(cli, ["template", "diff", "sales", version, *base])
        assert diff.exit_code == 0 and "+  query: SELECT 2" in diff.output

        restored = runner.invoke(cli, ["template", "rollback", "sales", version, *base])
        assert restored.exit_code == 0
        assert path.read_bytes() == original

    def test_rollback_to_unknown_version_fails_cleanly(self, tmp_path):
        TemplateManager(str(tmp_path)).save_config(make_config())
        result = CliRunner().invoke(
            cli,
            [
                "template", "rollback", "sales", "20260101T000000000000Z__save",
                "--templates-dir", str(tmp_path),
            ],
        )
        assert result.exit_code == 1
        assert "no version" in result.output
