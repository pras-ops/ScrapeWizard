import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from studio.backend.main import app
from studio.backend.db import get_session
from studio.backend.models import Setting, Test, Step, Run, StepResult

import os
from pathlib import Path

DB_FILE = Path("test_studio.db")
test_engine = create_engine(
    f"sqlite:///{DB_FILE}",
    connect_args={"check_same_thread": False}
)

@pytest.fixture(name="db_session")
def db_session_fixture():
    """Create a temporary SQLite DB file for routing tests and clean it up."""
    # Ensure any stale file is removed
    if DB_FILE.exists():
        try:
            os.remove(DB_FILE)
        except Exception:
            pass
            
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        # Truncate tables for test isolation
        from sqlmodel import delete
        for table in [StepResult, Run, Step, Test, Setting]:
            try:
                session.exec(delete(table))
            except Exception:
                pass
        session.commit()
        
        # Seed version robustly (avoids UNIQUE constraint error if file is locked)
        existing = session.get(Setting, "schema_version")
        if not existing:
            session.add(Setting(key="schema_version", value="1.2.0"))
            session.commit()
        yield session
        
    # Teardown
    if DB_FILE.exists():
        try:
            os.remove(DB_FILE)
        except Exception:
            pass

@pytest.fixture(name="client")
def client_fixture(db_session):
    """Overrides DB dependency to inject in-memory session."""
    def get_test_session():
        yield db_session
        
    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_health_check(client):
    """Verify backend health returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_settings_endpoints(client):
    """Verify loading, setting and testing connection of configs."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert response.json()["provider"] == "openai"
    assert response.json()["has_key"] is False
    
    # Save visual configs
    payload = {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "visual_threshold": 0.1,
        "retention": 15,
        "ai_mode": "Creation"
    }
    response = client.put("/settings", json=payload)
    assert response.status_code == 200
    
    # Get configuration settings back
    response = client.get("/settings")
    assert response.json()["provider"] == "anthropic"
    assert response.json()["model"] == "claude-3-5-sonnet"
    assert response.json()["visual_threshold"] == 0.1
    assert response.json()["retention"] == 15
    assert response.json()["ai_mode"] == "Creation"

def test_tests_crud(client):
    """Test full Test / Step CRUD endpoints sequence."""
    response = client.post("/tests", json={"url": "https://example.local", "name": "Studio Flow"})
    assert response.status_code == 200
    test_id = response.json()["id"]
    assert response.json()["name"] == "Studio Flow"
    
    response = client.get("/tests")
    assert len(response.json()) == 1
    assert response.json()[0]["step_count"] == 0
    
    # Update steps
    steps_payload = {
        "name": "Updated Studio Flow Name",
        "steps": [
            {
                "action": "navigate",
                "value": "https://example.local",
                "selectors": [],
                "assertions": [{"kind": "url", "value": "https://example.local"}]
            },
            {
                "action": "click",
                "value": "",
                "selectors": [{"kind": "css", "value": "#btn-login"}],
                "assertions": []
            }
        ]
    }
    response = client.put(f"/tests/{test_id}", json=steps_payload)
    assert response.status_code == 200
    
    response = client.get(f"/tests/{test_id}")
    assert response.json()["name"] == "Updated Studio Flow Name"
    assert len(response.json()["steps"]) == 2
    assert response.json()["steps"][0]["action"] == "navigate"
    assert response.json()["steps"][1]["action"] == "click"

def test_stats_and_runs_list(client, db_session):
    """Test dashboard stats compile correctly."""
    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json()["tests"] == 0
    assert response.json()["runs_today"] == 0
    assert response.json()["ai_spend"] == 0.0
