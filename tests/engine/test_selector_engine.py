import pytest
from scrapewizard.engine.selector_engine import (
    is_stable_class,
    is_stable_id,
    build_selector_ladder
)

def test_is_stable_class():
    # Stable semantic classes
    assert is_stable_class("btn-primary") is True
    assert is_stable_class("submit_button") is True
    assert is_stable_class("checkout-btn") is True
    assert is_stable_class("user-profile-card") is True

    # Tailwind & atomic utility classes (should be rejected)
    assert is_stable_class("flex") is False
    assert is_stable_class("grid") is False
    assert is_stable_class("mt-4") is False
    assert is_stable_class("mx-auto") is False
    assert is_stable_class("bg-red-500") is False
    assert is_stable_class("text-center") is False
    assert is_stable_class("hover:bg-blue-600") is False
    assert is_stable_class("md:items-center") is False
    assert is_stable_class("w-full") is False
    assert is_stable_class("h-full") is False

    # CSS-in-JS dynamic hashes (should be rejected)
    assert is_stable_class("css-1a2b3c") is False
    assert is_stable_class("sc-bdVaJa") is False
    assert is_stable_class("jsx-1234567") is False
    assert is_stable_class("styled-button-abcde12") is False

    # Digit-heavy / dynamic class names
    assert is_stable_class("btn-12345") is False  # 5 digits suffix
    assert is_stable_class("dynamic-9872") is False

def test_is_stable_id():
    # Stable descriptive IDs
    assert is_stable_id("checkout-btn") is True
    assert is_stable_id("search-input") is True
    assert is_stable_id("login-form") is True

    # Unstable / auto-generated IDs
    assert is_stable_id("123") is False
    assert is_stable_id("button-123456") is False
    assert is_stable_id("sc-12345") is False
    assert is_stable_id("row-987654") is False

def test_build_selector_ladder_stable_id():
    tag = "button"
    attributes = {"id": "checkout-btn", "class": "btn btn-primary btn-checkout flex mt-4"}
    text = "Checkout"
    context = {
        "parent": {"tag": "div", "classes": ["cart-footer", "flex", "p-4"]},
        "index_in_parent": 2
    }
    
    ladder = build_selector_ladder(tag, attributes, text, context)
    
    # 1. First selector should be the stable ID
    assert ladder[0]["kind"] == "css"
    assert ladder[0]["value"] == "#checkout-btn"
    assert ladder[0]["rank"] == 1
    
    # 2. Ladder should also include semantic class selector (filtering out flex/mt-4)
    class_selectors = [item for item in ladder if item["value"] == "button.btn.btn-primary.btn-checkout"]
    assert len(class_selectors) == 1
    assert class_selectors[0]["rank"] == 3

    # 3. Parent relative selector
    parent_selectors = [item for item in ladder if item["value"] == "div.cart-footer > button"]
    assert len(parent_selectors) == 1

    # 4. Text selector
    text_selectors = [item for item in ladder if item["value"] == ".//button[normalize-space(.)='Checkout']"]
    assert len(text_selectors) == 1
    assert text_selectors[0]["rank"] == 5

    # 5. Positional fallback selector
    position_selectors = [item for item in ladder if item["value"] == ".//div/button[3]"]
    assert len(position_selectors) == 1
    assert position_selectors[0]["rank"] == 6

def test_build_selector_ladder_data_testid():
    tag = "input"
    attributes = {"data-testid": "search-box", "class": "input-field border p-2"}
    text = ""
    context = {"parent": {"tag": "form", "classes": []}, "index_in_parent": 0}
    
    ladder = build_selector_ladder(tag, attributes, text, context)
    
    assert ladder[0]["kind"] == "css"
    assert ladder[0]["value"] == "input[data-testid='search-box']"
    assert ladder[0]["rank"] == 1
