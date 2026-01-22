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
        if has_storage:
            cookies_context = """- A 'storage_state.json' file exists. GENERATE CODE TO LOAD THIS STORAGE STATE (cookies + local storage) into the browser context. 
- IMPORTANT: Use absolute paths in the script so it can be run from any directory. 
- Use: script_dir = os.path.dirname(os.path.abspath(__file__))
- Use: storage_path = os.path.join(script_dir, 'storage_state.json')
- Use: output_dir = os.path.join(script_dir, 'output')
- Use: context = await browser.new_context(storage_state=storage_path)
"""
        elif has_cookies:
            cookies_context = "- A 'cookies.json' file exists. GENERATE CODE TO LOAD THESE COOKIES into the browser context BEFORE navigating to the target URL. Use absolute paths based on the script directory.\n"
        
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

Generate the full 'generated_scraper.py'.
IMPORTANT: Output ONLY valid Python code. No explanations, no markdown, no comments before the code.
The script must:
1. Save results to 'output/data.json'
2. Use asyncio and async_playwright
3. Be immediately runnable and robust to directory changes (use os.path.abspath and base all paths on the script's directory).
4. If multi-page pagination is requested, implement a robust loop that clicks the 'Next' button or equivalent.
5. DATA QUALITY (CRITICAL):
    - Filter out any 'null', empty, or malformed data records.
    - DEDUPLICATE records based on the primary fields (title/url).
    - If infinite scroll is used, set a hard limit of 50 interactions or check if node count stops growing.
6. Respect the 'browser_mode' from run_config. If 'headed', set headless=False.
{cookies_context}
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
