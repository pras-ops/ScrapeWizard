import json
import re
from pathlib import Path
from typing import Dict
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_CODEGEN
from scrapewizard.core.logging import log

class CodeGenerator:
    """
    Handles LLM Code Generation phase.
    """
    def __init__(self, project_dir: Path):
        self.client = LLMClient()
        self.project_dir = project_dir

    def generate(self, snapshot: Dict, understanding: Dict, run_config: Dict, scan_profile: Dict = None, interaction: Dict = None):
        """
        Generate the scraper based on inputs.
        """
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
        
        user_prompt = f"""
Analysis Snapshot: {json.dumps(snapshot, indent=2)}
LLM Understanding: {json.dumps(understanding, indent=2)}
Run Config: {json.dumps(run_config, indent=2)}
Behavioral Scan Profile: {json.dumps(scan_profile, indent=2) if scan_profile else "None"}
Interaction: {json.dumps(interaction, indent=2) if interaction else "None"}

Generate the full 'generated_scraper.py'.
IMPORTANT: Output ONLY valid Python code. No explanations, no markdown, no comments before the code.
The script must:
1. Save results to 'output/data.json'
2. Use asyncio and async_playwright
3. Be immediately runnable and robust to directory changes (use os.path.abspath and base all paths on the script's directory).
4. If multi-page pagination is requested, implement a robust loop that clicks the 'Next' button or equivalent.
5. Filter out any 'null' or empty data records before appending to the results list.
{cookies_context}
"""
        
        code = self.client.call(SYSTEM_PROMPT_CODEGEN, user_prompt, json_mode=False)
        
        # Save raw response
        self._save_log("codegen_response.py", code)
        
        # Robust extraction: find Python code block
        code = self._extract_python_code(code)
        
        output_path = self.project_dir / "generated_scraper.py"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        log(f"Scraper generated at {output_path}")
        return output_path

    def _save_log(self, filename: str, content: str):
        log_dir = self.project_dir / "llm_logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)

    def _extract_python_code(self, text: str) -> str:
        """
        Extract Python code from LLM response, handling markdown fences 
        and preamble text robustly.
        """
        # Try to find code in markdown fence
        pattern = r"```(?:python)?\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)
        if matches:
            # Return the longest match (likely the full script)
            code = max(matches, key=len)
            return code.strip()
        
        # If no fence, try to find where code actually starts
        # Look for common Python starts
        lines = text.split('\n')
        code_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ', 'class ', 'def ', 'async def ', '#!')):
                code_start = i
                break
        
        code = '\n'.join(lines[code_start:])
        code = code.strip()
        
        # Post-extraction fixes for common LLM hallucinations
        # 1. Broadly replace async_playwright package hits with the correct async path
        code = re.sub(r'\bfrom\s+async_playwright\b', 'from playwright.async_api', code, flags=re.IGNORECASE)
        code = re.sub(r'\bimport\s+async_playwright\b', 'from playwright.async_api import async_playwright', code, flags=re.IGNORECASE)
        
        # 2. Fix specific common mis-imports that the broad rule might leave weird
        code = re.sub(r'from\s+playwright\.async_api\s+import\s+async_playwright\.async_api', 'from playwright.async_api import async_playwright', code, flags=re.IGNORECASE)
        
        # 3. Ensure any stray 'async_playwright.async_api' (as a package) is corrected
        code = re.sub(r'\basync_playwright\.async_api\b', 'playwright.async_api', code, flags=re.IGNORECASE)

        return code
