import re
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_REPAIR
from scrapewizard.core.logging import log
from scrapewizard.utils.file_io import safe_read_json, safe_write_json

class RepairAgent:
    """Handles self-healing repair attempts using LLM analysis.
    
    This agent uses full project context, including previous failures and
    site metadata, to diagnose and fix failing scraper scripts.
    """
    def __init__(self, project_dir: Path):
        self.client = LLMClient()
        self.project_dir = Path(project_dir)

    def repair(self, script_path: Path, error_info: str, context: str = "") -> bool:
        """Attempts to repair a failing script using LLM intelligence.
        
        Args:
            script_path: Path to the script that failed.
            error_info: The error message or traceback from the failure.
            context: Optional additional context or user feedback.
            
        Returns:
            True if a repair was attempted, False otherwise.
        """
        log("Attempting repair...")
        
        with open(script_path, "r", encoding="utf-8") as f:
            current_code = f.read()

        # Load additional context from project files
        analysis = self._load_json("analysis_snapshot.json")
        understanding = self._load_json("llm_understanding.json")
        run_config = self._load_json("run_config.json")
        
        # Check for session state
        has_storage = (self.project_dir / "storage_state.json").exists()
        has_cookies = (self.project_dir / "cookies.json").exists()
        
        cookies_context = ""
        if has_storage:
            cookies_context = """- A 'storage_state.json' file exists. ENSURE the script loads THIS STORAGE STATE (cookies + local storage) into the browser context. 
- IMPORTANT: Use absolute paths in the script so it can be run from any directory. 
- Use: script_dir = os.path.dirname(os.path.abspath(__file__))
- Use: storage_path = os.path.join(script_dir, 'storage_state.json')
- Use: output_dir = os.path.join(script_dir, 'output')
- Use: context = await browser.new_context(storage_state=storage_path)
"""
        elif has_cookies:
            cookies_context = "- A 'cookies.json' file exists. ENSURE the script loads these cookies into the browser context. Use absolute paths based on the script directory.\n"
        
        user_prompt = f"""
Current Script:
{current_code}

Error Message:
{error_info}

{context if context else ""}

=== PROJECT CONTEXT ===

Analysis Snapshot (DOM structure):
{json.dumps(analysis, indent=2) if analysis else "Not available"}

LLM Understanding (field definitions):
{json.dumps(understanding, indent=2) if understanding else "Not available"}

Run Config (user selections):
{json.dumps(run_config, indent=2) if run_config else "Not available"}

=== INSTRUCTIONS ===
Fix the script. Output ONLY Python code. No explanations, no markdown.
Ensure:
1. Save results to 'output/data.json' using json.dump
2. Create output dir: os.makedirs('output', exist_ok=True)
3. Use proper async/await syntax
4. Use the correct CSS selectors from the analysis snapshot
5. Valid Python that runs immediately and is robust to directory changes (use os.path.abspath and base all paths on the script's directory).
6. Fix any pagination logic to ensure it actually clicks 'Next' if multi-page is required.
7. Filter out any 'null' or empty data records before appending to the results list.
{cookies_context}
"""
        
        new_code = self.client.call(SYSTEM_PROMPT_REPAIR, user_prompt, json_mode=False)
        
        # Save raw response
        self._save_log(f"repair_response_{int(time.time())}.py", new_code)
        
        # Robust extraction
        new_code = self.client.extract_python_code(new_code)
        
        # Save attempt
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(new_code)
            
        log("Repaired script saved.")
        return True

    def _save_log(self, filename: str, content: str) -> None:
        log_dir = self.project_dir / "llm_logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)

    def _load_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """Loads a JSON file from the project directory.
        
        Args:
            filename: Name of the JSON file to load.
            
        Returns:
            The parsed JSON data or None if loading fails.
        """
        path = self.project_dir / filename
        return safe_read_json(path, default=None)
