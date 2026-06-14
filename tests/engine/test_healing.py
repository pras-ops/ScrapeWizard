import pytest
from playwright.async_api import async_playwright
from scrapewizard.engine.fingerprint import capture_from_page
from scrapewizard.engine.healing import attempt_self_healing
from scrapewizard.engine.sandbox import SandboxRunner, StepResult

@pytest.mark.asyncio
async def test_self_healing_mutations(demo_server, tmp_path):
    """
    Verify that the deterministic self-healing engine correctly resolves mutated elements
    under class_rename, id_change, element_moved, and text_reword mutations.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        # 1. Bypass login by setting localStorage
        await page.goto(demo_server)
        await page.evaluate("""() => {
            localStorage.setItem("sw_logged_in", "true");
            localStorage.setItem("sw_username", "healing_tester");
        }""")

        # 2. Get baseline page and capture checkout button fingerprint
        await page.goto(demo_server)
        await page.wait_for_selector("#checkout-btn")
        checkout_el = await page.query_selector("#checkout-btn")
        assert checkout_el is not None
        
        fingerprint = await capture_from_page(page, checkout_el)
        fingerprint_dict = fingerprint.to_dict()

        # Verify selectors list contains primary selector
        assert len(fingerprint.selectors) > 0
        primary_selector = fingerprint.selectors[0]["value"]
        assert primary_selector == "#checkout-btn"

        # 3. Test Healing under Class Rename Mutation
        await page.goto(f"{demo_server}?mutate=class_rename")
        await page.wait_for_selector("#checkout-btn")
        
        # Verify the primary selector is still present but class has mutated
        btn_class = await page.get_attribute("#checkout-btn", "class")
        assert "btn-mutated-xyz" in btn_class
        
        # Clear data-sw-heal-id if any left
        await page.evaluate("() => document.querySelectorAll('[data-sw-heal-id]').forEach(el => el.removeAttribute('data-sw-heal-id'))")
        
        # Test healing directly
        healed_el = await attempt_self_healing(page, fingerprint_dict)
        assert healed_el is not None
        assert await healed_el.get_attribute("id") == "checkout-btn"

        # 4. Test Healing under ID Change Mutation
        await page.goto(f"{demo_server}?mutate=id_change")
        # In this mutation, the ID is order-btn-xyz instead of checkout-btn.
        # Primary selector #checkout-btn will fail to resolve.
        primary_loc = page.locator("#checkout-btn")
        assert await primary_loc.count() == 0

        # Attempt self-healing
        healed_el = await attempt_self_healing(page, fingerprint_dict)
        assert healed_el is not None
        assert await healed_el.inner_text() == "Checkout"

        # 5. Test Healing under Element Moved Mutation
        await page.goto(f"{demo_server}?mutate=element_moved")
        # Elements are moved to a different container
        primary_loc = page.locator("#checkout-btn")
        assert await primary_loc.count() == 1  # Still exists but container context changed
        
        healed_el = await attempt_self_healing(page, fingerprint_dict)
        assert healed_el is not None
        assert await healed_el.inner_text() == "Checkout"

        # 6. Test Healing under Text Reword Mutation
        await page.goto(f"{demo_server}?mutate=text_reword")
        # Text is reworded to "Order Now"
        healed_el = await attempt_self_healing(page, fingerprint_dict)
        assert healed_el is not None
        assert await healed_el.get_attribute("id") == "checkout-btn"

        # 7. Test Healing under Element Removed (should NOT heal to wrong element)
        await page.goto(f"{demo_server}?mutate=element_removed")
        healed_el = await attempt_self_healing(page, fingerprint_dict)
        assert healed_el is None  # Should not match anything because it's removed

        await browser.close()

@pytest.mark.asyncio
async def test_sandbox_runner_with_healing(demo_server, tmp_path):
    """
    Run SandboxRunner with a flow definition that requires self-healing.
    """
    # 1. Baseline flow definition
    # Contains a flow that navigates to the login screen, performs login, and clicks checkout.
    flow_json = tmp_path / "flow.json"
    
    # We first run a fresh run to get the fingerprint
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        await page.goto(demo_server)
        await page.fill("#username", "tester@scrapewizard.local")
        await page.fill("#password", "password123")
        await page.click("#login-submit-btn")
        await page.wait_for_selector("#checkout-btn")
        checkout_el = await page.query_selector("#checkout-btn")
        fp = await capture_from_page(page, checkout_el)
        fp_dict = fp.to_dict()
        await browser.close()

    test_definition = {
        "url": demo_server,
        "steps": [
            {
                "name": "navigate_to_start",
                "action": "navigate",
                "value": f"{demo_server}?mutate=id_change", # ID change mutation active
                "selectors": []
            },
            {
                "name": "fill_username",
                "action": "fill",
                "value": "tester@scrapewizard.local",
                "selectors": [{"kind": "css", "value": "#username"}]
            },
            {
                "name": "fill_password",
                "action": "fill",
                "value": "password123",
                "selectors": [{"kind": "css", "value": "#password"}]
            },
            {
                "name": "click_login",
                "action": "click",
                "selectors": [{"kind": "css", "value": "#login-submit-btn"}]
            },
            {
                "name": "click_checkout",
                "action": "click",
                "selectors": [{"kind": "css", "value": "#checkout-btn"}], # This will fail standard resolve and trigger healing
                "fingerprint": fp_dict
            }
        ]
    }

    runner = SandboxRunner(
        artifacts_dir=str(tmp_path / "artifacts"),
        baselines_dir=str(tmp_path / "baselines"),
        flow_name="test_healing_sandbox",
        headless=True
    )
    
    result = await runner.run(test_definition)
    assert result.status == "passed"
    
    # Verify the checkout step reports healed=True
    checkout_res = next(r for r in result.step_results if r.step_name == "click_checkout")
    assert checkout_res.status == "passed"
    assert checkout_res.healed is True
