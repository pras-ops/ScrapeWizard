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
    baselines_dir = tmp_path / "baselines"
    
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
    runner = SandboxRunner(artifacts_dir=str(artifacts_dir), baselines_dir=str(baselines_dir), headless=True)
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


@pytest.mark.asyncio
async def test_baselines_are_stable(demo_server, tmp_path):
    """
    Verify that running the sandbox twice with the same baselines_dir actually
    REUSES baselines from the first run (no re-baselining).
    """
    baselines_dir = tmp_path / "shared_baselines"

    # Minimal test def: just navigate
    test_def = {
        "url": demo_server,
        "steps": [{
            "name": "navigate_to_start",
            "action": "navigate",
            "value": demo_server,
            "selectors": [],
            "assertions": [{"kind": "url", "value": demo_server}]
        }]
    }

    # Run 1: should CREATE baselines
    runner1 = SandboxRunner(
        artifacts_dir=str(tmp_path / "run1"),
        baselines_dir=str(baselines_dir),
        headless=True,
    )
    result1 = await runner1.run(test_def)
    assert result1.status == "passed"

    # Baselines should now exist
    baseline_files = list(baselines_dir.glob("*.png"))
    assert len(baseline_files) > 0, "Baselines should have been created"

    # Record the modification time of the baseline
    mtime_after_run1 = baseline_files[0].stat().st_mtime

    # Run 2: should COMPARE against existing baselines (not overwrite)
    runner2 = SandboxRunner(
        artifacts_dir=str(tmp_path / "run2"),
        baselines_dir=str(baselines_dir),
        headless=True,
    )
    result2 = await runner2.run(test_def)
    assert result2.status == "passed"

    # Baseline file should NOT have been overwritten
    mtime_after_run2 = baseline_files[0].stat().st_mtime
    assert mtime_after_run1 == mtime_after_run2, "Baseline should not be overwritten on second run"

    # Visual diff should be 0 or very close (same page, same viewport)
    nav_step = result2.step_results[0]
    assert nav_step.visual_diff_score is not None
    assert nav_step.visual_diff_score < 0.1, f"Expected near-zero visual diff, got {nav_step.visual_diff_score}"


def test_visual_check_diff_detection(tmp_path):
    """Unit test for the visual comparison engine's diff detection."""
    from PIL import Image
    from scrapewizard.engine.checks.visual import perform_visual_check

    baselines_dir = tmp_path / "baselines"
    diff_dir = tmp_path / "diffs"

    # Create a solid red baseline image
    img1 = Image.new("RGB", (100, 100), color="red")
    baselines_dir.mkdir(parents=True, exist_ok=True)
    img1.save(baselines_dir / "step_1.png")

    # Create a solid blue "current" screenshot
    current_path = tmp_path / "current.png"
    img2 = Image.new("RGB", (100, 100), color="blue")
    img2.save(current_path)

    # They should differ significantly
    score, diff_path = perform_visual_check(
        str(current_path), "step_1", str(baselines_dir), str(diff_dir)
    )
    assert score > 0.5, f"Expected high diff score for red vs blue, got {score}"
    assert diff_path is not None
    assert Path(diff_path).exists()

    # Now compare identical images — diff should be 0
    score2, diff_path2 = perform_visual_check(
        str(baselines_dir / "step_1.png"), "step_1", str(baselines_dir), str(diff_dir)
    )
    assert score2 == 0.0
    assert diff_path2 is None

