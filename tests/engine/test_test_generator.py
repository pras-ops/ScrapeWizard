import ast
import json
import subprocess
import pytest
from pathlib import Path
from scrapewizard.engine.test_generator import TestGenerator

def test_test_generator_compilation(tmp_path):
    """Test generating a test script from a mock flow.json and verify it is syntactically valid."""
    flow_json = tmp_path / "flow.json"
    generated_py = tmp_path / "test_generated_flow.py"
    
    mock_flow = {
        "url": "http://localhost:8001",
        "steps": [
            {
                "action": "fill",
                "value": "tester@scrapewizard.local",
                "fingerprint": {
                    "tag": "input",
                    "attributes": {"id": "username", "type": "text"},
                    "text": "",
                    "context": {},
                    "selectors": [{"kind": "css", "value": "#username", "rank": 1}]
                },
                "assertions": [{"kind": "visible", "value": "#username"}]
            },
            {
                "action": "fill",
                "value": "***MASKED***",
                "fingerprint": {
                    "tag": "input",
                    "attributes": {"id": "password", "type": "password"},
                    "text": "",
                    "context": {},
                    "selectors": [{"kind": "css", "value": "#password", "rank": 1}]
                },
                "assertions": [{"kind": "visible", "value": "#password"}]
            },
            {
                "action": "click",
                "value": None,
                "fingerprint": {
                    "tag": "button",
                    "attributes": {"id": "login-submit-btn"},
                    "text": "Login",
                    "context": {},
                    "selectors": [{"kind": "css", "value": "#login-submit-btn", "rank": 1}]
                },
                "assertions": []
            }
        ]
    }
    
    with open(flow_json, "w", encoding="utf-8") as f:
        json.dump(mock_flow, f)
        
    generator = TestGenerator(str(flow_json))
    test_def = generator.generate()
    
    # Check step names
    assert test_def["url"] == "http://localhost:8001"
    assert len(test_def["steps"]) == 4 # 1 navigation + 3 user actions
    assert test_def["steps"][0]["name"] == "navigate_to_start"
    assert test_def["steps"][1]["name"] == "fill_username_0"
    assert test_def["steps"][2]["name"] == "fill_password_1"
    assert test_def["steps"][3]["name"] == "click_login_submit_btn_2"
    
    # Export and check syntax
    rendered = generator.export_pytest(str(generated_py))
    assert generated_py.exists()
    
    # Try compiling using AST to verify valid Python syntax
    try:
        ast.parse(rendered)
    except SyntaxError as e:
        pytest.fail(f"Generated test code has syntax errors: {e}")

@pytest.mark.asyncio
async def test_generated_file_execution(demo_server, tmp_path):
    """Generate a test against the live demo server, save it, and run it using pytest."""
    from scrapewizard.engine.recorder import InteractiveRecorder
    import asyncio
    
    flow_json = tmp_path / "flow.json"
    screenshots_dir = tmp_path / "screenshots"
    generated_py = tmp_path / "test_generated_flow.py"
    
    # 1. Record a simple flow
    recorder = InteractiveRecorder(
        output_path=str(flow_json),
        screenshots_dir=str(screenshots_dir),
        headless=True
    )
    
    async def drive_recorder():
        while recorder.page is None:
            await asyncio.sleep(0.05)
        await recorder.page.wait_for_selector("#username")
        await recorder.page.fill("#username", "tester@scrapewizard.local")
        await recorder.page.locator("#username").blur()
        while len(recorder.steps) < 1:
            await asyncio.sleep(0.05)
        await recorder.page.close()

    drive_task = asyncio.create_task(drive_recorder())
    await recorder.start(demo_server)
    await drive_task
    
    # 2. Generate the python test file
    generator = TestGenerator(str(flow_json))
    generator.export_pytest(str(generated_py))
    
    assert generated_py.exists()
    
    # 3. Run the generated test file using subprocess calling the Python 3.12 pytest
    # We use -v and -s to print outputs
    res = subprocess.run(
        ["C:\\Python312\\python.exe", "-m", "pytest", str(generated_py), "-v"],
        capture_output=True,
        text=True
    )
    
    print("STDOUT of generated test execution:\n", res.stdout)
    print("STDERR of generated test execution:\n", res.stderr)
    
    assert res.returncode == 0, f"Generated test failed to run or pass. stdout: {res.stdout}"
