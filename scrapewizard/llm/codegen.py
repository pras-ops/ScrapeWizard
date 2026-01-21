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

    def generate(self, snapshot: Dict, understanding: Dict, run_config: Dict, interaction: Dict = None):
        """
        Generate the scraper based on inputs.
        """
        log("Generating scraper code...")
        
        user_prompt = f"""
Analysis Snapshot: {json.dumps(snapshot, indent=2)}
LLM Understanding: {json.dumps(understanding, indent=2)}
Run Config: {json.dumps(run_config, indent=2)}
Interaction: {json.dumps(interaction, indent=2) if interaction else "None"}

Generate the full 'generated_scraper.py'.
IMPORTANT: Output ONLY valid Python code. No explanations, no markdown, no comments before the code.
The script must:
1. Save results to 'output/data.json'
2. Use asyncio and async_playwright
3. Be immediately runnable
"""
        
        code = self.client.call(SYSTEM_PROMPT_CODEGEN, user_prompt, json_mode=False)
        
        # Robust extraction: find Python code block
        code = self._extract_python_code(code)
        
        output_path = self.project_dir / "generated_scraper.py"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        log(f"Scraper generated at {output_path}")
        return output_path

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
        
        code = code.strip()
        
        # Post-extraction fixes for common LLM hallucinations
        code = code.replace("from async_playwright import", "from playwright.async_api import")
        code = code.replace("import async_playwright", "from playwright.async_api import async_playwright")
        
        return code
