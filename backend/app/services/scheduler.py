"""Job scheduler service using APScheduler with SQLite persistence.

Handles scheduled tasks like digest generation, stale memory alerts, and connection suggestions.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import text

from ..db.core import get_engine

logger = logging.getLogger(__name__)


class ScheduledJob:
    """Represents a scheduled job."""
    
    def __init__(
        self,
        job_id: str,
        job_type: str,
        name: str,
        schedule_type: str,
        schedule_value: str,
        handler: str,
        handler_args: dict | None = None,
        description: str | None = None,
        is_enabled: bool = True,
    ):
        self.id = job_id
        self.job_type = job_type
        self.name = name
        self.description = description
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.handler = handler
        self.handler_args = handler_args or {}
        self.is_enabled = is_enabled
        self.last_run_at: datetime | None = None
        self.next_run_at: datetime | None = None
        self.run_count = 0
        self.error_count = 0
        self.last_error: str | None = None


class Scheduler:
    """Simple job scheduler with SQLite persistence."""
    
    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._task = None
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a job handler function."""
        self._handlers[name] = handler
        logger.debug(f"Registered scheduler handler: {name}")
    
    def _get_handler(self, handler_name: str) -> Callable | None:
        """Get a registered handler by name."""
        return self._handlers.get(handler_name)
    
    async def create_job(
        self,
        job_type: str,
        name: str,
        schedule_type: str,
        schedule_value: str,
        handler: str,
        handler_args: dict | None = None,
        description: str | None = None,
        is_enabled: bool = True,
    ) -> ScheduledJob:
        """Create a new scheduled job."""
        job_id = str(uuid4())
        
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO scheduled_jobs (
                    id, job_type, name, description, schedule_type, schedule_value,
                    handler, handler_args, is_enabled, next_run_at
                ) VALUES (
                    :id, :job_type, :name, :description, :schedule_type, :schedule_value,
                    :handler, :handler_args, :is_enabled, :next_run_at
                )
            """), {
                "id": job_id,
                "job_type": job_type,
                "name": name,
                "description": description,
                "schedule_type": schedule_type,
                "schedule_value": schedule_value,
                "handler": handler,
                "handler_args": json.dumps(handler_args) if handler_args else None,
                "is_enabled": is_enabled,
                "next_run_at": self._calculate_next_run(schedule_type, schedule_value),
            })
            conn.commit()
        
        job = ScheduledJob(
            job_id=job_id,
            job_type=job_type,
            name=name,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            handler=handler,
            handler_args=handler_args,
            description=description,
            is_enabled=is_enabled,
        )
        job.next_run_at = self._calculate_next_run(schedule_type, schedule_value)
        
        logger.info(f"Created scheduled job: {name} ({job_id})")
        return job
    
    async def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get a job by ID."""
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM scheduled_jobs WHERE id = :id"
            ), {"id": job_id}).fetchone()
            
            if not result:
                return None
            
            return self._row_to_job(result)
    
    async def list_jobs(
        self,
        job_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[ScheduledJob]:
        """List all scheduled jobs."""
        engine = get_engine()
        with engine.connect() as conn:
            query = "SELECT * FROM scheduled_jobs WHERE 1=1"
            params: dict[str, Any] = {}
            
            if job_type:
                query += " AND job_type = :job_type"
                params["job_type"] = job_type
            
            if enabled_only:
                query += " AND is_enabled = TRUE"
            
            query += " ORDER BY created_at DESC"
            
            results = conn.execute(text(query), params).fetchall()
            return [self._row_to_job(row) for row in results]
    
    async def update_job(
        self,
        job_id: str,
        is_enabled: bool | None = None,
        schedule_type: str | None = None,
        schedule_value: str | None = None,
    ) -> ScheduledJob | None:
        """Update a scheduled job."""
        engine = get_engine()
        with engine.connect() as conn:
            updates = ["updated_at = CURRENT_TIMESTAMP"]
            params: dict[str, Any] = {"id": job_id}
            
            if is_enabled is not None:
                updates.append("is_enabled = :is_enabled")
                params["is_enabled"] = is_enabled
            
            if schedule_type and schedule_value:
                updates.append("schedule_type = :schedule_type")
                updates.append("schedule_value = :schedule_value")
                updates.append("next_run_at = :next_run_at")
                params["schedule_type"] = schedule_type
                params["schedule_value"] = schedule_value
                params["next_run_at"] = self._calculate_next_run(schedule_type, schedule_value)
            
            conn.execute(text(f"""
                UPDATE scheduled_jobs SET {', '.join(updates)} WHERE id = :id
            """), params)
            conn.commit()
        
        return await self.get_job(job_id)
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a scheduled job."""
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(
                "DELETE FROM scheduled_jobs WHERE id = :id"
            ), {"id": job_id})
            conn.commit()
            return result.rowcount > 0
    
    async def run_job(self, job_id: str) -> dict[str, Any]:
        """Manually run a job immediately."""
        job = await self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        return await self._execute_job(job)
    
    async def _execute_job(self, job: ScheduledJob) -> dict[str, Any]:
        """Execute a job and update its status."""
        handler = self._get_handler(job.handler)
        if not handler:
            error = f"Handler not found: {job.handler}"
            await self._record_job_error(job.id, error)
            return {"success": False, "error": error}
        
        try:
            import asyncio
            
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**job.handler_args)
            else:
                result = handler(**job.handler_args)
            
            await self._record_job_success(job.id)
            return {"success": True, "result": result}
            
        except Exception as e:
            error = str(e)
            logger.exception(f"Job {job.id} failed: {error}")
            await self._record_job_error(job.id, error)
            return {"success": False, "error": error}
    
    async def _record_job_success(self, job_id: str) -> None:
        """Record successful job execution."""
        engine = get_engine()
        with engine.connect() as conn:
            # Get current job to calculate next run
            result = conn.execute(text(
                "SELECT schedule_type, schedule_value FROM scheduled_jobs WHERE id = :id"
            ), {"id": job_id}).fetchone()
            
            if result:
                next_run = self._calculate_next_run(result[0], result[1])
                
                conn.execute(text("""
                    UPDATE scheduled_jobs SET
                        last_run_at = CURRENT_TIMESTAMP,
                        next_run_at = :next_run,
                        run_count = run_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """), {"id": job_id, "next_run": next_run})
                conn.commit()
    
    async def _record_job_error(self, job_id: str, error: str) -> None:
        """Record job execution error."""
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE scheduled_jobs SET
                    last_run_at = CURRENT_TIMESTAMP,
                    error_count = error_count + 1,
                    last_error = :error,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """), {"id": job_id, "error": error})
            conn.commit()
    
    def _calculate_next_run(self, schedule_type: str, schedule_value: str) -> datetime:
        """Calculate the next run time based on schedule."""
        now = datetime.utcnow()
        
        if schedule_type == "interval":
            # schedule_value is in minutes
            minutes = int(schedule_value)
            return now + timedelta(minutes=minutes)
        
        elif schedule_type == "daily":
            # schedule_value is HH:MM
            hour, minute = map(int, schedule_value.split(":"))
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        
        elif schedule_type == "weekly":
            # schedule_value is "DAY HH:MM" (e.g., "monday 09:00")
            parts = schedule_value.split()
            day_name = parts[0].lower()
            hour, minute = map(int, parts[1].split(":"))
            
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            target_day = days.index(day_name)
            current_day = now.weekday()
            
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            
            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_run
        
        elif schedule_type == "cron":
            # For cron expressions, default to next hour
            return now + timedelta(hours=1)
        
        else:
            # Default to 1 hour from now
            return now + timedelta(hours=1)
    
    def _row_to_job(self, row) -> ScheduledJob:
        """Convert a database row to a ScheduledJob."""
        job = ScheduledJob(
            job_id=row[0],
            job_type=row[1],
            name=row[2],
            description=row[3],
            schedule_type=row[4],
            schedule_value=row[5],
            handler=row[6],
            handler_args=json.loads(row[7]) if row[7] else None,
            is_enabled=bool(row[8]),
        )
        job.last_run_at = row[9]
        job.next_run_at = row[10]
        job.run_count = row[11] or 0
        job.error_count = row[12] or 0
        job.last_error = row[13]
        return job
    
    async def start(self) -> None:
        """Start the scheduler background task."""
        import asyncio
        
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")
    
    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        import asyncio
        
        while self._running:
            try:
                await self._check_and_run_due_jobs()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            # Check every minute
            await asyncio.sleep(60)
    
    async def _check_and_run_due_jobs(self) -> None:
        """Check for and run any due jobs."""
        engine = get_engine()
        with engine.connect() as conn:
            results = conn.execute(text("""
                SELECT id FROM scheduled_jobs
                WHERE is_enabled = TRUE
                AND next_run_at <= CURRENT_TIMESTAMP
            """)).fetchall()
        
        for row in results:
            job_id = row[0]
            try:
                job = await self.get_job(job_id)
                if job:
                    logger.info(f"Running scheduled job: {job.name}")
                    await self._execute_job(job)
            except Exception as e:
                logger.error(f"Failed to run job {job_id}: {e}")


# Global scheduler instance
_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the global scheduler."""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler() -> None:
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    await scheduler.stop()
