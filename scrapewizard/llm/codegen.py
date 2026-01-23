import json
import re
from pathlib import Path
from typing import Dict, Any
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_CODEGEN
from scrapewizard.core.logging import log
from scrapewizard.utils.file_io import safe_write_json

class CodeGenerator:
    """Handles the LLM Code Generation phase.
    
    This agent takes the analyzed data structure and generates a fully
    functional Playwright script tailored to the target site's layout.
    """
    def __init__(self, project_dir: Path, wizard_mode: bool = False):
        self.client = LLMClient()
        self.project_dir = project_dir
        self.wizard_mode = wizard_mode

    def generate(self, snapshot: Dict[str, Any], understanding: Dict[str, Any], run_config: Dict[str, Any], scan_profile: Dict[str, Any] = None, interaction: Dict[str, Any] = None) -> Path:
        """Generates the scraper based on analysis and configuration.
        
        Args:
            snapshot: The DOM snapshot metadata.
            understanding: The LLM's understanding of the site structure.
            run_config: User-provided configuration for the run.
            scan_profile: Behavioral signals and hostility assessment.
            interaction: Records of user interactions (login, etc.).
            
        Returns:
            The Path to the generated Python script.
        """
        if not self.wizard_mode:
            log("Generating scraper code...")
        
        # Check for session state
        has_storage = (self.project_dir / "storage_state.json").exists()
        has_cookies = (self.project_dir / "cookies.json").exists()
        
        cookies_context = ""
        if (self.project_dir / "storage_state.json").exists():
            cookies_context = "- A 'storage_state.json' file exists and will be automatically loaded by the BaseScraper runtime.\n"
        
        # Hostility Override - Make hostility score visible to LLM
        hostility_score = scan_profile.get("hostility_score", 0) if scan_profile else 0
        hostility_context = ""
        if hostility_score >= 40:
            hostility_context = f"""
⚠️ HOSTILITY ALERT: This site has a hostility score of {hostility_score}/100.
Bot defense mechanisms detected. You MUST use headed mode (headless=False).
DO NOT use headless mode under any circumstances.
"""
        
        user_prompt = f"""
Analysis Snapshot: {json.dumps(snapshot, indent=2)}
LLM Understanding: {json.dumps(understanding, indent=2)}
Run Config: {json.dumps(run_config, indent=2)}
Behavioral Scan Profile: {json.dumps(scan_profile, indent=2) if scan_profile else "None"}
Interaction: {json.dumps(interaction, indent=2) if interaction else "None"}

{hostility_context}
{cookies_context}

Generate the 'generated_scraper.py' implementation.
IMPORTANT: Output ONLY valid Python code. No explanations, no markdown.

REQUIRED STRUCTURE:
```python
from scrapewizard_runtime import BaseScraper

class Scraper(BaseScraper):
    async def navigate(self):
        # Implementation...
        pass

    async def get_items(self):
        # Implementation...
        return []

    async def parse_item(self, item):
        # Implementation...
        return {{}}

if __name__ == "__main__":
    Scraper(
        mode="{run_config.get('browser_mode', 'headless')}", 
        output_format="{run_config.get('format', 'json')}", 
        pagination_config={json.dumps(run_config.get('pagination_config', {"mode": "first_page", "max_pages": 1}))},
        pagination_meta={json.dumps(understanding.get("pagination", {}))}
    ).run()
```

DATA QUALITY RULES:
1. Prefer stable CSS selectors over dynamic classes.
2. Use `await self.runtime.smart_wait(selector)` before querying elements.
3. If a field is missing, set its value to `None` in the result dictionary.
4. **CRITICAL**: Only return `None` from `parse_item` if the item is purely decorative or contains NO data fields at all. If any data field is found, return the record.
5. Ensure the script structure strictly follows the REQUIRED STRUCTURE above.
"""
        
        code = self.client.call(SYSTEM_PROMPT_CODEGEN, user_prompt, json_mode=False)
        
        # Save raw response
        self._save_log("codegen_response.py", code)
        
        # Robust extraction: find Python code block
        code = self.client.extract_python_code(code)
        
        output_path = self.project_dir / "generated_scraper.py"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        if not self.wizard_mode:
            log(f"Scraper generated at {output_path}")
        return output_path

    def _save_log(self, filename: str, content: str) -> None:
        log_dir = self.project_dir / "llm_logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)
