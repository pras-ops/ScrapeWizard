import json
from pathlib import Path
from typing import Dict
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_UNDERSTANDING
from scrapewizard.core.logging import log

class UnderstandingAgent:
    """
    Handles the 'Understanding & Feasibility' phase using LLM.
    """
    def __init__(self, project_dir: Path, wizard_mode: bool = False):
        self.client = LLMClient()
        self.project_dir = project_dir
        self.wizard_mode = wizard_mode

    def analyze(self, snapshot_data: Dict, scan_profile: Dict = None, interaction_log: Dict = None) -> Dict:
        """
        Send snapshot to LLM to understand structure.
        """
        if not self.wizard_mode:
            log("Sending analysis snapshot to LLM...")
        
        user_prompt = f"""
        Here is the analysis of the webpage:
        {json.dumps(snapshot_data, indent=2)}
        
        Behavioral Scan Profile:
        {json.dumps(scan_profile, indent=2) if scan_profile else "None"}
        
        Interaction Log:
        {json.dumps(interaction_log, indent=2) if interaction_log else "None"}
        """
        
        response_text = self.client.call(SYSTEM_PROMPT_UNDERSTANDING, user_prompt)
        
        # Save raw response
        self._save_log("call1_response.json", response_text)
        
        parsed = self.client.parse_json(response_text)
        
        # Save understanding artifact
        with open(self.project_dir / "llm_understanding.json", "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2)
            
        return parsed

    def _save_log(self, filename: str, content: str):
        log_dir = self.project_dir / "llm_logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)
