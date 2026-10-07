import pytest
from playwright.async_api import async_playwright
from scrapewizard.engine.fingerprint import capture_from_page
from scrapewizard.engine.healing import attempt_self_healing

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
