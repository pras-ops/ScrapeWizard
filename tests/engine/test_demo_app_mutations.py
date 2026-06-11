import json
import socket
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from playwright.async_api import async_playwright

from scrapewizard.demo_app.app import app
from scrapewizard.engine.fingerprint import ElementFingerprint, compute_dom_neighborhood_hash
from scrapewizard.engine.selector_engine import build_selector_ladder

def get_free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="module")
def demo_server():
    """Starts the FastAPI demo app in a background thread."""
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    
    # Wait for server to boot
    time.sleep(1.0)
    
    yield f"http://127.0.0.1:{port}"
    
    server.should_exit = True
    thread.join(timeout=2.0)

@pytest.mark.asyncio
async def test_demo_app_interactive_and_fingerprint(demo_server):
    """
    Tests the login flow, element selection/fingerprinting using the bridge script,
    and checks if the extracted payload matches our expectations.
    """
    bridge_path = Path("studio/bridge/engine.js")
    assert bridge_path.exists(), "engine.js must exist"
    bridge_script = bridge_path.read_text(encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        # Expose a selection callback to Python
        received_selection = []
        async def on_element_selected(payload_json: str):
            received_selection.append(json.loads(payload_json))

        await context.expose_function("onElementSelected", on_element_selected)
        await context.add_init_script(bridge_script)

        # 1. Navigate to the Login Screen
        await page.goto(demo_server)
        assert "ScrapeWizard Demo Portal" in await page.title()
        
        # 2. Fill login inputs & submit
        await page.fill("#username", "tester@scrapewizard.local")
        await page.fill("#password", "password123")
        await page.click("#login-submit-btn")
        
        # 3. Wait for dashboard page elements to render
        await page.wait_for_selector("#checkout-btn")
        
        # 4. Trigger selection via Javascript Bridge
        await page.evaluate("""() => {
            window.setStudioMode('PICKER');
            // Trigger selection of checkout button
            window.studioBridge.handlePickerClick(document.getElementById('checkout-btn'));
        }""")
        
        # Wait a brief moment for the callback to fire
        await page.wait_for_timeout(500)
        
        assert len(received_selection) == 1
        payload = received_selection[0]
        
        # Verify basic payload fields
        assert payload["tag"] == "button"
        assert "btn-checkout" in payload["attributes"]["class"]
        assert payload["text"] == "Checkout"
        
        # Verify geometry
        geometry = payload["geometry"]
        assert geometry["w"] > 0
        assert geometry["h"] > 0
        assert geometry["viewport"] == [1280, 720]
        assert 0.0 <= geometry["x_pct"] <= 1.0
        assert 0.0 <= geometry["y_pct"] <= 1.0

        # Verify context details
        context_data = payload["context"]
        assert context_data["parent"]["tag"] == "td"
        assert context_data["index_in_parent"] == 0 or context_data["index_in_parent"] == 1
        assert len(context_data["ancestors"]) > 0
        
        # Hash parent HTML
        parent_html = payload["parent_html"]
        assert parent_html.strip().startswith("<td")
        
        # 5. Build Python ElementFingerprint instance and verify
        fingerprint = ElementFingerprint(payload)
        assert fingerprint.tag == "button"
        assert fingerprint.width > 0
        assert fingerprint.parent_tag == "td"
        
        # Test hash generation
        h1 = compute_dom_neighborhood_hash(parent_html)
        h2 = compute_dom_neighborhood_hash(parent_html.replace("   ", "")) # clean space test
        assert len(h1) == 64
        assert h1 == h2  # Hash should be stable ignoring whitespace differences

        # Test python-side selector ladder builder from the payload
        ladder = build_selector_ladder(
            fingerprint.tag,
            fingerprint.attributes,
            fingerprint.text,
            fingerprint.context
        )
        assert len(ladder) > 0
        assert ladder[0]["value"] == "#checkout-btn"

        await browser.close()

@pytest.mark.asyncio
async def test_demo_app_mutations(demo_server):
    """
    Verify that query parameters trigger the correct DOM mutations in the demo app dashboard.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Fast login bypass by setting localStorage
        page = await context.new_page()
        await page.goto(demo_server)
        await page.evaluate("""() => {
            localStorage.setItem("sw_logged_in", "true");
            localStorage.setItem("sw_username", "mutation_tester");
        }""")

        # 1. Test class_rename mutation
        await page.goto(f"{demo_server}?mutate=class_rename")
        await page.wait_for_selector("#checkout-btn")
        btn_class = await page.get_attribute("#checkout-btn", "class")
        assert "btn-mutated-xyz" in btn_class
        assert "btn-checkout" not in btn_class

        # 2. Test id_change mutation
        await page.goto(f"{demo_server}?mutate=id_change")
        # should find by the new id
        await page.wait_for_selector("#order-btn-xyz")
        assert await page.is_visible("#order-btn-xyz")

        # 3. Test element_moved mutation
        await page.goto(f"{demo_server}?mutate=element_moved")
        await page.wait_for_selector("#alternative-target-container #checkout-btn")
        assert await page.is_visible("#alternative-target-container #checkout-btn")

        # 4. Test text_reword mutation
        await page.goto(f"{demo_server}?mutate=text_reword")
        await page.wait_for_selector("#checkout-btn")
        btn_text = await page.inner_text("#checkout-btn")
        assert btn_text == "Order Now"

        # 5. Test insert_sibling mutation
        await page.goto(f"{demo_server}?mutate=insert_sibling")
        await page.wait_for_selector("#cancel-btn")
        assert await page.is_visible("#cancel-btn")

        # 6. Test attribute_changed mutation
        await page.goto(f"{demo_server}?mutate=attribute_changed")
        await page.wait_for_selector("#checkout-btn")
        testid = await page.get_attribute("#checkout-btn", "data-testid")
        role = await page.get_attribute("#checkout-btn", "role")
        assert testid == "checkout-order-submit"
        assert role == "submit-btn"

        # 7. Test element_removed mutation
        await page.goto(f"{demo_server}?mutate=element_removed")
        await page.wait_for_timeout(500)
        assert await page.query_selector("#checkout-btn") is None

        await browser.close()
