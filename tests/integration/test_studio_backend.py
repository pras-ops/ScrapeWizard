import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from studio.backend.main import app
from studio.backend.db import get_session
from studio.backend.models import Setting, Test, Step, Run, StepResult

import os
from pathlib import Path

from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

@pytest.fixture(name="db_session")
def db_session_fixture():
    """Create an in-memory SQLite DB session for routing tests."""
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
        
        # Seed version robustly
        existing = session.get(Setting, "schema_version")
        if not existing:
            session.add(Setting(key="schema_version", value="1.2.0"))
            session.commit()
        yield session

@pytest.fixture(name="client")
def client_fixture(db_session, monkeypatch):
    """Overrides DB dependency to inject in-memory session and isolates configuration."""
    from scrapewizard.core.config import ConfigManager
    monkeypatch.setattr(ConfigManager, "load_config", lambda: {"provider": "openai", "model": "gpt-4-turbo"})
    monkeypatch.setattr(ConfigManager, "get_api_key", lambda provider: "")
    
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

def test_studio_parity_validator(tmp_path, monkeypatch):
    """Verify that the parity validator calculates correct drift rates and status."""
    import json
    from studio.backend.test_runner import StudioParityValidator
    from scrapewizard.runtime.tester import ScriptTester
    from scrapewizard.core.project_manager import ProjectManager
    
    # 1. Create a dummy recording baseline
    recording_file = tmp_path / "recording.jsonl"
    with open(recording_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "extract", "data": {"title": "Book 1", "price": "£10"}}) + "\n")
        f.write(json.dumps({"type": "extract", "data": {"title": "Book 2", "price": "£20"}}) + "\n")
        
    # 2. Mock project setup
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    (project_dir / "output").mkdir()
    
    # Write actual output that has drift (Book 2 is missing price, and Book 1 has mismatching price)
    actual_data = [
        {"title": "Book 1", "price": "£15"}, # mismatching price (1 drift)
        {"title": "Book 2"}                  # missing price (1 drift)
    ]
    
    output_file = project_dir / "output" / "data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(actual_data, f)
        
    # Create dummy generated_scraper.py so validator thinks it exists
    with open(project_dir / "generated_scraper.py", "w") as f:
        f.write("# dummy")
        
    # Mock ScriptTester.run_test to succeed
    monkeypatch.setattr(ScriptTester, "run_test", lambda script_path, cwd, wizard_mode: (True, "mock-run-success"))
    
    # Mock Projects Root
    monkeypatch.setattr(ProjectManager, "PROJECTS_ROOT", tmp_path)
    
    # 3. Validate
    validator = StudioParityValidator()
    report = validator.validate(str(project_dir), recording_file)
    
    assert report["status"] == "drift_detected"
    # Total keys checked in baseline: 4 (Book 1 title/price, Book 2 title/price)
    # Drifted keys: 2 (Book 1 price mismatched, Book 2 price missing)
    # Drift rate should be 2/4 = 50%
    assert report["drift_rate"] == 0.5
    assert "price" in report["failing_selectors"]
    assert "title" in report["stable_selectors"]
