import asyncio
import json
import pytest
from pathlib import Path
from scrapewizard.engine.recorder import InteractiveRecorder
from scrapewizard.engine.test_generator import TestGenerator
from scrapewizard.engine.sandbox import SandboxRunner

@pytest.mark.asyncio
async def test_sandbox_runner_golden_flow(demo_server, tmp_path):
    """
    E2E integration test:
    1. Record a simple flow against the FastAPI demo portal.
    2. Convert recorded flow into a test definition.
    3. Run sandbox runner against the definition.
    4. Assert results are recorded, screenshots generated, and checks run.
    """
    flow_json = tmp_path / "flow.json"
    screenshots_dir = tmp_path / "screenshots"
    artifacts_dir = tmp_path / "sandbox_artifacts"
    
    # 1. Record
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
    
    assert flow_json.exists()
    
    # 2. Generate
    generator = TestGenerator(str(flow_json))
    test_def = generator.generate()
    
    # 3. Run sandbox
    runner = SandboxRunner(artifacts_dir=str(artifacts_dir), headless=True)
    run_result = await runner.run(test_def)
    
    # 4. Assertions
    assert run_result.status == "passed"
    assert len(run_result.step_results) == 2 # navigate + fill
    
    step0 = run_result.step_results[0]
    assert step0.step_name == "navigate_to_start"
    assert step0.status == "passed"
    assert step0.screenshot_path is not None
    assert Path(step0.screenshot_path).exists()
    assert step0.console_errors is not None
    assert step0.network_errors is not None
    assert step0.a11y_violations is not None
    
    step1 = run_result.step_results[1]
    assert step1.step_name.startswith("fill_username_")
    assert step1.status == "passed"
    assert step1.screenshot_path is not None
    assert Path(step1.screenshot_path).exists()
    assert step1.console_errors is not None
    assert step1.network_errors is not None
    assert step1.a11y_violations is not None
