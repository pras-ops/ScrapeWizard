import json
from pathlib import Path
from typing import Dict, Any
from scrapewizard.llm.client import LLMClient
from scrapewizard.llm.prompts import SYSTEM_PROMPT_UNDERSTANDING
from scrapewizard.core.logging import log
from scrapewizard.utils.file_io import safe_write_json

class UnderstandingAgent:
    """Handles the 'Understanding & Feasibility' phase using LLM analysis.
    
    This agent takes a DOM snapshot and behavioral signals to identify the
    underlying data structure and suggest relevant fields for scraping.
    """
    def __init__(self, project_dir: Path, wizard_mode: bool = False):
        self.client = LLMClient()
        self.project_dir = project_dir
        self.wizard_mode = wizard_mode

    def analyze(self, snapshot_data: Dict[str, Any], scan_profile: Dict[str, Any] = None, interaction_log: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyzes the page structure using the LLM.
        
        Args:
            snapshot_data: The DOM snapshot extracted during reconnaissance.
            scan_profile: The behavioral signals (mutations, network, etc.).
            interaction_log: Records of user interactions (login, navigation).
            
        Returns:
            A dictionary containing the LLM's understanding of the data structure.
        """
        if not self.wizard_mode:
            log("Sending analysis snapshot to LLM...")
        
        user_prompt = f"""
        Detect the core data structure. For each field found in 'available_fields', 
        add a 'suggested' boolean (true if it's a primary data point like title/price).
        
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
        safe_write_json(self.project_dir / "llm_understanding.json", parsed)
            
        return parsed

    def _save_log(self, filename: str, content: str):
        log_dir = self.project_dir / "llm_logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)
