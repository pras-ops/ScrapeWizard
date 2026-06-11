import re
from typing import Dict, List, Any, Optional

# Regex for checking if an ID/class is auto-generated or dynamic
# E.g. matches long numbers, hex hashes (hex of length 6+), uuid, CSS-in-JS style prefixes
DYNAMIC_ID_PATTERN = re.compile(
    r"(?:^[0-9]+$)"                              # Purely numeric
    r"|(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4})"        # Part of a UUID
    r"|(?:sc-|css-|jsx-|styled-|__theme-)"       # Common CSS-in-JS prefixes
    r"|(?:-[a-fA-F0-9]{5,10}$)"                 # Hex-like suffix (e.g. -1a2b3c)
    r"|(?:\d{3,})"                               # 3 or more digits in a row (often dynamic indices/timestamps)
)

# Common utility-first classes (e.g. Tailwind CSS) to exclude
UTILITY_EXACT_MATCHES = {
    # Layout & Display
    "flex", "grid", "block", "inline", "hidden", "absolute", "relative", "fixed", "static", "sticky",
    "table", "flow-root", "contents",
    # Alignment
    "items-center", "items-start", "items-end", "items-baseline", "items-stretch",
    "justify-center", "justify-start", "justify-end", "justify-between", "justify-around", "justify-evenly",
    "content-center", "content-start", "content-end", "content-between", "content-around", "content-stretch",
    "self-auto", "self-start", "self-end", "self-center", "self-stretch", "self-baseline",
    # Width/Height defaults
    "w-full", "h-full", "w-screen", "h-screen", "w-auto", "h-auto",
    # Transitions
    "transition", "duration-75", "duration-100", "duration-150", "duration-200", "duration-300",
    "ease-linear", "ease-in", "ease-out", "ease-in-out",
}

# Prefixes for utility/atomic classes
UTILITY_PREFIXES = (
    "m-", "mt-", "mr-", "mb-", "ml-", "mx-", "my-",
    "p-", "pt-", "pr-", "pb-", "pl-", "px-", "py-",
    "w-", "h-", "bg-", "text-", "border-", "rounded-", "shadow-", "gap-",
    "grid-cols-", "grid-rows-", "col-span-", "row-span-",
    "font-", "leading-", "tracking-", "opacity-", "z-", "cursor-",
    "align-", "valign-", "space-x-", "space-y-",
    "hover:", "focus:", "active:", "md:", "lg:", "sm:", "xl:", "2xl:",
    "dark:", "disabled:"
)

def is_stable_id(element_id: Optional[str]) -> bool:
    """Determine if an ID attribute is stable (not dynamic or auto-generated)."""
    if not element_id:
        return False
    if DYNAMIC_ID_PATTERN.search(element_id):
        return False
    return True

def is_stable_class(class_name: str) -> bool:
    """
    Check if a class name is stable (i.e. not Tailwind utility, not CSS-in-JS hash).
    """
    if not class_name:
        return False
    
    # 1. Clean format check
    if not re.match(r"^[a-zA-Z0-9_-]+$", class_name):
        return False
        
    # 2. Reject CSS-in-JS dynamic prefixes/hashes
    if DYNAMIC_ID_PATTERN.search(class_name):
        return False
        
    # 3. Reject exact Tailwind/utility matches
    if class_name in UTILITY_EXACT_MATCHES:
        return False
        
    # 4. Reject utility prefixes (e.g. mt-4, bg-red-500)
    if class_name.startswith(UTILITY_PREFIXES):
        return False
        
    return True

def clean_xpath_text(text: str) -> str:
    """Sanitize and escape text for use in XPath queries."""
    # Escape single quotes using xpath concat if necessary
    if "'" in text:
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{p}'" for p in parts) + ")"
    return f"'{text}'"

def build_selector_ladder(
    tag: str, 
    attributes: Dict[str, Any], 
    text: str, 
    context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Construct a ranked selector ladder (CSS & XPath strategies) for an element.
    Returns a list of dicts: {"kind": "css"|"xpath", "value": str, "rank": int}
    """
    tag = tag.lower()
    ladder = []
    
    # 1. Stable ID
    element_id = attributes.get("id")
    if is_stable_id(element_id):
        ladder.append({
            "kind": "css",
            "value": f"#{element_id}",
            "rank": 1
        })
        
    # 2. Stable Test/QA attributes (highest rank)
    for test_attr in ["data-testid", "data-test", "data-qa"]:
        val = attributes.get(test_attr)
        if val:
            ladder.append({
                "kind": "css",
                "value": f"{tag}[{test_attr}='{val}']",
                "rank": 1 if test_attr != "data-qa" else 2
            })
            
    # 3. Aria-label / Accessibility attributes
    aria_label = attributes.get("aria-label")
    if aria_label:
        ladder.append({
            "kind": "css",
            "value": f"{tag}[aria-label='{aria_label}']",
            "rank": 2
        })
        
    # 4. Itemprop attribute
    itemprop = attributes.get("itemprop")
    if itemprop:
        ladder.append({
            "kind": "css",
            "value": f"{tag}[itemprop='{itemprop}']",
            "rank": 2
        })

    # 5. Semantic classes
    classes_str = attributes.get("class", "")
    if classes_str:
        raw_classes = classes_str.split() if isinstance(classes_str, str) else list(classes_str)
        stable_classes = [c for c in raw_classes if is_stable_class(c)]
        if stable_classes:
            ladder.append({
                "kind": "css",
                "value": f"{tag}.{'.'.join(stable_classes)}",
                "rank": 3
            })
            
    # 6. Anchored relative CSS (parent context)
    parent = context.get("parent", {})
    parent_tag = parent.get("tag")
    if parent_tag:
        parent_tag = parent_tag.lower()
        parent_classes = parent.get("classes", [])
        stable_parent_classes = [c for c in parent_classes if is_stable_class(c)]
        
        # Build parent CSS segment
        parent_css = parent_tag
        if stable_parent_classes:
            parent_css += f".{'.'.join(stable_parent_classes)}"
            
        # Add parent-anchored selector
        ladder.append({
            "kind": "css",
            "value": f"{parent_css} > {tag}",
            "rank": 4
        })

    # 7. Anchored Text XPath
    cleaned_text = text.strip()
    if cleaned_text and len(cleaned_text) < 60:
        xpath_text = clean_xpath_text(cleaned_text)
        # Match element by normalized text contents
        ladder.append({
            "kind": "xpath",
            "value": f".//{tag}[normalize-space(.)={xpath_text}]",
            "rank": 5
        })

    # 8. Positional XPath fallback (last resort local selector)
    index = context.get("index_in_parent", 0)
    parent_tag = parent.get("tag")
    if parent_tag:
        parent_tag = parent_tag.lower()
        # Relative positional path: e.g. .//div/button[1]
        ladder.append({
            "kind": "xpath",
            "value": f".//{parent_tag}/{tag}[{index + 1}]",
            "rank": 6
        })
    else:
        # Absolute positional path fallback
        ladder.append({
            "kind": "xpath",
            "value": f".//{tag}[{index + 1}]",
            "rank": 7
        })

    # De-duplicate selectors by value while maintaining best ranks
    seen = set()
    unique_ladder = []
    for item in sorted(ladder, key=lambda x: x["rank"]):
        if item["value"] not in seen:
            seen.add(item["value"])
            unique_ladder.append(item)
            
    return unique_ladder
