import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

class Setting(SQLModel, table=True):
    """Global configuration settings for ScrapeWizard Studio."""
    key: str = Field(primary_key=True)
    value: str

class Test(SQLModel, table=True):
    """User-recorded automated testing flows."""
    __test__ = False
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    url: str
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class Step(SQLModel, table=True):
    """An individual recorded step within a Test flow."""
    id: Optional[int] = Field(default=None, primary_key=True)
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    order: int  # Step order execution
    action: str  # e.g., 'navigate', 'click', 'fill'
    value: Optional[str] = None
    selectors: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    assertions: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    fingerprint: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))

class Run(SQLModel, table=True):
    """An execution instance of a Test flow."""
    id: Optional[int] = Field(default=None, primary_key=True)
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    status: str  # 'queued', 'running', 'passed', 'failed', 'error'
    started_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    finished_at: Optional[datetime.datetime] = None
    duration_ms: Optional[int] = None
    ai_calls: int = 0
    ai_cost_usd: float = 0.0

class StepResult(SQLModel, table=True):
    """Quality check evaluation results for a step execution in a Run."""
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", ondelete="CASCADE")
    step_name: str
    status: str  # 'passed', 'failed', 'error'
    duration_ms: int
    screenshot_path: Optional[str] = None
    visual_diff_score: Optional[float] = None
    console_errors: List[str] = Field(default=[], sa_column=Column(JSON))
    network_errors: List[str] = Field(default=[], sa_column=Column(JSON))
    a11y_violations: List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    healed: bool = False
    error_message: Optional[str] = None
