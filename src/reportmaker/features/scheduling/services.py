"""Scheduler service using APScheduler."""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import logging

from reportmaker.shared.file_utils import ensure_directory
from reportmaker.shared.logging import get_logger
from reportmaker.features.report_generation.services import generate_report
from reportmaker.features.report_generation.models import ReportConfig
from reportmaker.features.scheduling.models import ScheduleConfig, ScheduleStatus
from reportmaker.features.scheduling.exceptions import (
    SchedulingError,
    ScheduleNotFoundError,
    ScheduleAlreadyExistsError,
)

logger = get_logger(__name__)


class SchedulerService:
    """Manages schedules and the APScheduler instance."""

    def __init__(self, schedules_file: str = "schedules.yaml"):
        self.schedules_file = Path(schedules_file)
        self.scheduler: Optional[BlockingScheduler] = None
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

    def _get_trigger(self, cfg: ScheduleConfig):
        """Return an APScheduler trigger based on config."""
        if cfg.cron:
            return CronTrigger.from_crontab(cfg.cron)
        elif cfg.interval_seconds:
            return IntervalTrigger(seconds=cfg.interval_seconds)
        else:
            raise ValueError("No trigger defined")

    def _job_function(self, schedule_name: str) -> None:
        """The function that runs the report."""
        cfg = self._schedules.get(schedule_name)
        if not cfg:
            logger.error(f"Schedule '{schedule_name}' not found")
            return
        if not cfg.enabled:
            logger.info(f"Schedule '{schedule_name}' is disabled, skipping")
            return

        logger.info(f"Running scheduled report '{schedule_name}'")
        try:
            result = generate_report(
                cfg.report_config,
                output_dir="./reports",  # could be configurable
                parameters=cfg.parameters,
            )
            if result.success:
                logger.info(f"Scheduled report '{schedule_name}' completed: {result.output_path}")
                # Update last_run
                cfg.last_run = datetime.now()
                self._save_schedules()
            else:
                logger.error(f"Scheduled report '{schedule_name}' failed: {result.error}")
        except Exception as e:
            logger.error(f"Error running scheduled report '{schedule_name}': {e}", exc_info=True)

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

    def start(self, foreground: bool = True) -> None:
        """Start the scheduler."""
        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        self.scheduler = BlockingScheduler() if foreground else BlockingScheduler()
        # Add all enabled schedules
        for name, cfg in self._schedules.items():
            if cfg.enabled:
                self._add_job_to_scheduler(cfg)

        # Add event listeners for logging
        def event_listener(event):
            if event.exception:
                logger.error(f"Job {event.job_id} failed: {event.exception}")
            else:
                logger.info(f"Job {event.job_id} executed successfully")

        self.scheduler.add_listener(event_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

        # Start the scheduler
        logger.info("Starting scheduler (foreground mode)" if foreground else "Starting scheduler (background mode)")
        try:
            self.scheduler.start()
            logger.info("Scheduler started, press Ctrl+C to stop")
            if foreground:
                # Blocking call
                self.scheduler._thread.join()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            if self.scheduler:
                self.scheduler.shutdown()
                self.scheduler = None
