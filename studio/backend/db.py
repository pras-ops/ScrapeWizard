import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from scrapewizard.core.config import ConfigManager

# SQLite database path inside ~/.scrapewizard/
DB_DIR = ConfigManager.CONFIG_DIR
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "studio.db"

# Create the engine
database_url = f"sqlite:///{DB_PATH}"
engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False}  # Safe for SQLite with multiple threads
)

def init_db():
    """Create all SQLModel tables in SQLite if they do not exist."""
    SQLModel.metadata.create_all(engine)
    
    # Store schema version if not set
    from studio.backend.models import Setting
    with Session(engine) as session:
        version_setting = session.get(Setting, "schema_version")
        if not version_setting:
            version_setting = Setting(key="schema_version", value="1.0.0")
            session.add(version_setting)
            session.commit()

def get_session():
    """Dependency for obtaining database sessions in FastAPI route handlers."""
    with Session(engine) as session:
        yield session
