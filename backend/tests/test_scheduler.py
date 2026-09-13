from app.core.config import Settings
from app.scheduler.runtime import create_scheduler


def test_scheduler_registers_non_overlapping_operational_jobs() -> None:
    settings = Settings(_env_file=None, fcm_enabled=True, fcm_project_id="test-project")

    scheduler = create_scheduler(settings)
    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {
        "process-rainfall-observations",
        "retry-notification-deliveries",
    }
    assert jobs["process-rainfall-observations"].max_instances == 1
    assert jobs["process-rainfall-observations"].coalesce is True


def test_scheduler_omits_fcm_retry_when_fcm_is_disabled() -> None:
    scheduler = create_scheduler(Settings(_env_file=None, fcm_enabled=False))

    assert [job.id for job in scheduler.get_jobs()] == ["process-rainfall-observations"]
