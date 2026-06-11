"""Guard test: the Orchestrator must construct from a fresh project directory.

This is verification-ladder rung 1 (PLATFORM_PLAN.md §14.4). It exists because a
missing top-level import once made `scrapewizard build` crash with NameError for
every user while the rest of the suite stayed green — no test exercised the path
a real user takes. This test is intentionally minimal: construction only.
"""
import json

import pytest

from scrapewizard.core.orchestrator import Orchestrator


@pytest.fixture
def project_dir(tmp_path):
    session = {
        "project_id": "construction-test",
        "url": "https://example.com",
        "state": "INIT",
    }
    (tmp_path / "session.json").write_text(json.dumps(session), encoding="utf-8")
    return tmp_path


def test_orchestrator_constructs(project_dir):
    orchestrator = Orchestrator(project_dir)
    assert orchestrator.session["project_id"] == "construction-test"
    assert orchestrator.session["state"] == "INIT"


def test_orchestrator_rejects_invalid_project(tmp_path):
    with pytest.raises(ValueError):
        Orchestrator(tmp_path)  # no session.json


def test_pagination_config_helper(project_dir):
    orchestrator = Orchestrator(project_dir)
    assert orchestrator._build_pagination_config("first_page") == {
        "mode": "first_page",
        "max_pages": 1,
    }
    assert orchestrator._build_pagination_config("limit_5") == {
        "mode": "first_page",
        "max_pages": 5,
    }
    assert orchestrator._build_pagination_config("all_pages") == {
        "mode": "all",
        "max_pages": 50,
    }
