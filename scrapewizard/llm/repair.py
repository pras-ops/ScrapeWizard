import re
import json
from pathlib import Path
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_REPAIR
from scrapewizard.core.logging import log

class RepairAgent:
    """
    Handles self-healing repair attempts using LLM.
    Includes full project context for better repairs.
    """
    def __init__(self, project_dir: Path):
        self.client = LLMClient()
        self.project_dir = Path(project_dir)

    def repair(self, script_path: Path, error_info: str, context: str = "") -> bool:
        """
        Attempt to repair a failing script.
        Includes analysis_snapshot and llm_understanding for richer context.
        """
        log("Attempting repair...")
        
        with open(script_path, "r", encoding="utf-8") as f:
            current_code = f.read()

        # Load additional context from project files
        analysis = self._load_json("analysis_snapshot.json")
        understanding = self._load_json("llm_understanding.json")
        run_config = self._load_json("run_config.json")
        
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
5. Valid Python that runs immediately
"""
        
        new_code = self.client.call(SYSTEM_PROMPT_REPAIR, user_prompt, json_mode=False)
        
        # Robust extraction
        new_code = self._extract_python_code(new_code)
        
        # Save attempt
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(new_code)
            
        log("Repaired script saved.")
        return True

    def _load_json(self, filename: str):
        """Load a JSON file from project directory."""
        path = self.project_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return None
        return None

    def _extract_python_code(self, text: str) -> str:
        """Extract Python code from LLM response."""
        # Try to find code in markdown fence
        pattern = r"```(?:python)?\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)
        if matches:
            code = max(matches, key=len)
            return code.strip()
        
        # If no fence, find where code starts
        lines = text.split('\n')
        code_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ', 'class ', 'def ', 'async def ', '#!')):
                code_start = i
                break
        
        code = code.strip()
        
        # Post-extraction fixes for common LLM hallucinations
        code = code.replace("from async_playwright import", "from playwright.async_api import")
        code = code.replace("import async_playwright", "from playwright.async_api import async_playwright")
        
        return code
