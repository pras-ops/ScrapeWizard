import re
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
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

    def repair(self, script_path: Path, error_info: str, context: str = "", bad_cols: Optional[List[str]] = None) -> bool:
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
        if (self.project_dir / "storage_state.json").exists():
            cookies_context = "- A 'storage_state.json' file exists and will be automatically loaded by the BaseScraper runtime.\n"
        
        field_fix_instruction = ""
        if bad_cols:
            field_fix_instruction = f"\nCRITICAL: The following fields are returning NO DATA. Focus on fixing their selectors: {', '.join(bad_cols)}\n"

        user_prompt = f"""
Current Plugin Code:
{current_code}

Error Message:
{error_info}
{field_fix_instruction}
{context if context else ""}

=== PROJECT CONTEXT ===

Analysis Snapshot (DOM structure):
{json.dumps(analysis, indent=2) if analysis else "Not available"}

LLM Understanding (field definitions):
{json.dumps(understanding, indent=2) if understanding else "Not available"}

Run Config (user selections):
{json.dumps(run_config, indent=2) if run_config else "Not available"}

=== INSTRUCTIONS ===
Fix the plugin. Output ONLY Python code. No explanations, no markdown.
Ensure the plugin subclasses `BaseScraper` and implements the required methods correctly.
Use `await self.runtime.smart_wait()` if elements are missing or not loaded.
{cookies_context}

CRITICAL: The script MUST end with this exact block (with values filled):
if __name__ == "__main__":
    Scraper(mode="...", output_format="...", pagination_config={{...}}, pagination_meta={{...}}).run()
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
