import os
from pathlib import Path
from typing import List, Dict, Any
from scrapewizard.core.logging import log

# Read the bundled script content once and cache it in memory
AXE_SCRIPT_PATH = Path(__file__).parent / "axe.min.js"
AXE_SCRIPT_CONTENT = None

if AXE_SCRIPT_PATH.exists():
    with open(AXE_SCRIPT_PATH, "r", encoding="utf-8") as f:
        AXE_SCRIPT_CONTENT = f.read()

async def perform_a11y_check(page) -> List[Dict[str, Any]]:
    """
    Inject axe-core into the target Playwright page, run analysis,
    and return a structured list of accessibility violations.
    """
    global AXE_SCRIPT_CONTENT
    
    if not AXE_SCRIPT_CONTENT:
        if AXE_SCRIPT_PATH.exists():
            with open(AXE_SCRIPT_PATH, "r", encoding="utf-8") as f:
                AXE_SCRIPT_CONTENT = f.read()
        else:
            log("axe.min.js not found, skipping accessibility check", level="warning")
            return []

    try:
        # Inject the axe-core library
        await page.evaluate(AXE_SCRIPT_CONTENT)
        
        # Run accessibility analysis
        # axe.run() returns a promise, so we evaluate it asynchronously
        results = await page.evaluate("async () => { return await axe.run(); }")
        
        violations = []
        for violation in results.get("violations", []):
            nodes = []
            for node in violation.get("nodes", []):
                nodes.append({
                    "html": node.get("html"),
                    "target": node.get("target"),
                    "failure_summary": node.get("failureSummary")
                })
                
            violations.append({
                "id": violation.get("id"),
                "impact": violation.get("impact"),
                "description": violation.get("description"),
                "help": violation.get("help"),
                "help_url": violation.get("helpUrl"),
                "nodes": nodes
            })
            
        return violations
        
    except Exception as e:
        log(f"Accessibility validation failed: {e}", level="warning")
        return []
