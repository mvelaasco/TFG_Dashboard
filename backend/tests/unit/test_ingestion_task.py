import pytest


def test_module_imports():
    """The ingestion task module should import without errors."""
    from infrastructure.workers.ingestion_task import hourly_ingestion, _run_hourly_ingestion
    assert callable(hourly_ingestion)
    assert callable(_run_hourly_ingestion)


def test_task_is_registered():
    """The task should be discoverable by Celery."""
    from infrastructure.workers.ingestion_task import hourly_ingestion
    assert hourly_ingestion.name is not None
    assert "hourly_ingestion" in hourly_ingestion.name


def test_task_has_celery_attributes():
    """Verify Celery task attributes are set."""
    from infrastructure.workers.ingestion_task import hourly_ingestion
    assert hasattr(hourly_ingestion, 'run')
    # Task should accept no arguments
    import inspect
    sig = inspect.signature(hourly_ingestion.run)
    # Should have no required params (self is the task instance)
    assert len([p for p in sig.parameters.values() if p.default is inspect.Parameter.empty and p.name != 'self']) == 0
