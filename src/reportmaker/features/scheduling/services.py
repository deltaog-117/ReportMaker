"""Scheduler service using APScheduler."""

import time
import yaml
from pathlib import Path
from typing import Callable, List, Optional
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.features.report_generation.services import generate_report
from reportmaker.features.report_generation.models import ReportResult
from reportmaker.features.scheduling.exceptions import (
    SchedulingError,
    ScheduleNotFoundError,
    ScheduleAlreadyExistsError,
)
from reportmaker.features.scheduling.models import RunRecord, ScheduleConfig, ScheduleStatus
from reportmaker.features.scheduling.repositories import RunHistoryStore

logger = get_logger(__name__)


class SchedulerService:
    """Manages schedules and the APScheduler instance."""

    def __init__(
        self,
        schedules_file: str = "schedules.yaml",
        on_report_generated: Optional[Callable[[ScheduleConfig, ReportResult], None]] = None,
        history_file: Optional[str] = None,
    ):
        """Load schedules from `schedules_file`, creating it lazily on first save."""
        self.schedules_file = Path(schedules_file)
        self.scheduler: Optional[BlockingScheduler | BackgroundScheduler] = None
        self.on_report_generated = on_report_generated
        self.history = RunHistoryStore(
            history_file or str(self.schedules_file.with_name("run_history.yaml"))
        )
        self._load_schedules()

    def _load_schedules(self) -> None:
        """Load schedules from YAML file."""
        if self.schedules_file.exists():
            with open(self.schedules_file, "r") as f:
                data = yaml.safe_load(f) or {}
                self._schedules = {name: ScheduleConfig(**cfg) for name, cfg in data.items()}
        else:
            self._schedules = {}

    def _save_schedules(self) -> None:
        """Save schedules to YAML file."""
        ensure_directory(self.schedules_file.parent)
        data = {name: cfg.model_dump() for name, cfg in self._schedules.items()}
        with open(self.schedules_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def list_schedules(self) -> List[ScheduleStatus]:
        """Return a list of all schedules with status."""
        statuses = []
        for name, cfg in self._schedules.items():
            trigger_type = "cron" if cfg.cron else "interval"
            trigger_value = cfg.cron if cfg.cron else f"every {cfg.interval_seconds}s"
            statuses.append(ScheduleStatus(
                name=name,
                enabled=cfg.enabled,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                last_run=cfg.last_run,
                next_run=cfg.next_run,
            ))
        return statuses

    def add_schedule(self, config: ScheduleConfig) -> None:
        """Add a new schedule."""
        if config.name in self._schedules:
            raise ScheduleAlreadyExistsError(f"Schedule '{config.name}' already exists")
        self._schedules[config.name] = config
        self._save_schedules()
        # If scheduler is running, add the job immediately
        if self.scheduler and self.scheduler.running:
            self._add_job_to_scheduler(config)

    def remove_schedule(self, name: str) -> None:
        """Remove a schedule by name."""
        if name not in self._schedules:
            raise ScheduleNotFoundError(f"Schedule '{name}' not found")
        del self._schedules[name]
        self._save_schedules()
        # Remove from scheduler if running
        if self.scheduler and self.scheduler.running:
            job_id = f"schedule_{name}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

    def set_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a schedule, updating a running scheduler live."""
        if name not in self._schedules:
            raise ScheduleNotFoundError(f"Schedule '{name}' not found")
        cfg = self._schedules[name]
        cfg.enabled = enabled
        self._save_schedules()
        if self.scheduler and self.scheduler.running:
            job_id = f"schedule_{name}"
            if enabled:
                self._add_job_to_scheduler(cfg)
            elif self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

    def list_run_history(
        self, schedule_name: Optional[str] = None, limit: int = 50
    ) -> List[RunRecord]:
        """Return recent run records, newest first."""
        return self.history.list_recent(schedule_name, limit)

    def _get_trigger(self, cfg: ScheduleConfig):
        """Return an APScheduler trigger based on config."""
        if cfg.cron:
            try:
                return CronTrigger.from_crontab(cfg.cron)
            except Exception as e:
                raise SchedulingError(
                    f"Schedule '{cfg.name}' has an invalid cron expression '{cfg.cron}': {e}"
                ) from e
        elif cfg.interval_seconds:
            return IntervalTrigger(seconds=cfg.interval_seconds)
        else:
            raise SchedulingError(f"Schedule '{cfg.name}' has no trigger defined")

    def _job_function(self, schedule_name: str) -> None:
        """Run the scheduled report and record the outcome."""
        cfg = self._schedules.get(schedule_name)
        if not cfg:
            logger.error(f"Schedule '{schedule_name}' not found")
            return
        if not cfg.enabled:
            logger.info(f"Schedule '{schedule_name}' is disabled, skipping")
            return

        logger.info(f"Running scheduled report '{schedule_name}'")
        started_at = datetime.now()
        started_perf = time.perf_counter()
        try:
            result = generate_report(
                cfg.report_config,
                output_dir="./reports",  # could be configurable
                parameters=cfg.parameters,
            )
        except Exception as e:
            logger.error(f"Error running scheduled report '{schedule_name}': {e}", exc_info=True)
            self._record_run(
                schedule_name, started_at, time.perf_counter() - started_perf,
                success=False, error=str(e),
            )
            return

        duration = time.perf_counter() - started_perf
        if result.success:
            logger.info(f"Scheduled report '{schedule_name}' completed: {result.output_path}")
            # Update last_run
            cfg.last_run = datetime.now()
            self._save_schedules()
            self._record_run(
                schedule_name, started_at, duration,
                success=True, output_path=result.output_path,
            )
            if self.on_report_generated:
                self.on_report_generated(cfg, result)
        else:
            logger.error(f"Scheduled report '{schedule_name}' failed: {result.error}")
            self._record_run(
                schedule_name, started_at, duration, success=False, error=result.error,
            )

    def _record_run(
        self,
        schedule_name: str,
        started_at: datetime,
        duration_seconds: float,
        success: bool,
        output_path: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Append a run record, without letting a write failure affect the job."""
        try:
            self.history.append(RunRecord(
                schedule_name=schedule_name,
                started_at=started_at,
                duration_seconds=duration_seconds,
                success=success,
                output_path=output_path,
                error=error,
            ))
        except Exception:
            logger.exception(f"Failed to record run history for '{schedule_name}'")

    def _add_job_to_scheduler(self, cfg: ScheduleConfig) -> None:
        """Add a single job to the scheduler."""
        if not self.scheduler:
            return
        job_id = f"schedule_{cfg.name}"
        trigger = self._get_trigger(cfg)
        self.scheduler.add_job(
            self._job_function,
            trigger,
            args=[cfg.name],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=60,
        )

    def _populate_jobs(self) -> None:
        """Add every enabled schedule as a job and wire up event logging."""
        for cfg in self._schedules.values():
            if cfg.enabled:
                self._add_job_to_scheduler(cfg)

        def event_listener(event):
            if event.exception:
                logger.error(f"Job {event.job_id} failed: {event.exception}")
            else:
                logger.info(f"Job {event.job_id} executed successfully")

        self.scheduler.add_listener(event_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def start(self, foreground: bool = True) -> None:
        """Start the scheduler in the calling thread; blocks until Ctrl+C.

        Intended for the CLI daemon (``reportmaker schedule start``), which
        has no other work to do while the scheduler runs.
        """
        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        self.scheduler = BlockingScheduler()
        self._populate_jobs()

        logger.info("Starting scheduler (blocking)")
        try:
            self.scheduler.start()  # blocks until shutdown() or KeyboardInterrupt
            logger.info("Scheduler started, press Ctrl+C to stop")
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            if self.scheduler:
                self.scheduler.shutdown()
                self.scheduler = None

    def start_background(self) -> None:
        """Start the scheduler in a daemon thread and return immediately.

        Intended for embedding in a long-running host process (the GUI),
        which owns its own event loop and must not be blocked.
        """
        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        self.scheduler = BackgroundScheduler()
        self._populate_jobs()
        self.scheduler.start()
        logger.info("Scheduler started in the background")

    def stop(self) -> None:
        """Stop the scheduler, if one is running."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.scheduler = None
