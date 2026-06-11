import asyncio
import json
import pytest
from pathlib import Path
from scrapewizard.engine.recorder import InteractiveRecorder

@pytest.mark.asyncio
async def test_recorder_flow(demo_server, tmp_path):
    flow_json = tmp_path / "flow.json"
    screenshots_dir = tmp_path / "screenshots"
    
    recorder = InteractiveRecorder(
        output_path=str(flow_json),
        screenshots_dir=str(screenshots_dir),
        headless=True
    )
    
    async def drive_recorder():
        # Wait for page to launch and initialize
        while recorder.page is None:
            await asyncio.sleep(0.05)
        
        # Wait for target selector to appear
        await recorder.page.wait_for_selector("#username")
        
        # Drive input interaction
        await recorder.page.fill("#username", "tester@scrapewizard.local")
        await recorder.page.locator("#username").blur()
        while len(recorder.steps) < 1:
            await asyncio.sleep(0.05)
        
        # Drive password interaction
        await recorder.page.fill("#password", "secret123")
        await recorder.page.locator("#password").blur()
        while len(recorder.steps) < 2:
            await asyncio.sleep(0.05)
        
        # Click login button
        await recorder.page.click("#login-submit-btn")
        while len(recorder.steps) < 3:
            await asyncio.sleep(0.05)
        
        # Wait for dashboard
        await recorder.page.wait_for_selector("#checkout-btn")
        
        # Click checkout button
        await recorder.page.click("#checkout-btn")
        while len(recorder.steps) < 4:
            await asyncio.sleep(0.05)
        
        # Stop recording by closing the page
        await recorder.page.close()

    drive_task = asyncio.create_task(drive_recorder())
    
    # Run the recorder (will navigate and run until closed)
    await recorder.start(demo_server)
    await drive_task
    
    # Verify file was written
    assert flow_json.exists()
    
    with open(flow_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert data["url"] == demo_server
    assert "steps" in data
    steps = data["steps"]
    
    # Validate structure
    assert len(steps) >= 3
    
    # Check password masking
    password_steps = [s for s in steps if s["action"] == "fill" and s["fingerprint"]["attributes"].get("type") == "password"]
    assert len(password_steps) > 0
    for ps in password_steps:
        assert ps["value"] == "***MASKED***"
        
    # Check assertions list format
    for step in steps:
        assert "action" in step
        assert "value" in step
        assert "fingerprint" in step
        assert "assertions" in step
        assert len(step["assertions"]) > 0
        assert any(a["kind"] == "visible" for a in step["assertions"])

    # Verify screenshot crops
    crops = list(screenshots_dir.glob("crop_*.png"))
    assert len(crops) > 0
