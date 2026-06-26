import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.runtime.tester import ScriptTester
from scrapewizard.core.config import ConfigManager

class StudioParityValidator:
    """Validates Studio-generated scrapers against recordings to detect drift."""
    
    def validate(self, project_id: str, recording_path: Path) -> Dict[str, Any]:
        """
        Runs the Studio-generated scraper and compares output to the recording.
        
        Args:
            project_id: The ID of the project/scraper to test.
            recording_path: Path to the .jsonl recording file.
            
        Returns:
            A report containing drift rate and selector stability metrics.
        """
        # 1. Load recording (expected data baseline)
        expected_items = self._load_recording_baseline(recording_path)
        
        # 2. Resolve project directory
        project_dir = Path(project_id)
        if not project_dir.exists():
            project_dir = ProjectManager.PROJECTS_ROOT / project_id
            
        if not project_dir.exists():
            if ProjectManager.PROJECTS_ROOT.exists():
                matches = [p for p in ProjectManager.PROJECTS_ROOT.iterdir() if p.is_dir() and project_id in p.name]
                if matches:
                    matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    project_dir = matches[0]
            
        scraper_path = project_dir / "generated_scraper.py"
        if not scraper_path.exists():
            studio_projects_dir = ConfigManager.CONFIG_DIR / "projects"
            if studio_projects_dir.exists():
                matches = [p for p in studio_projects_dir.iterdir() if p.is_dir() and project_id in p.name]
                if matches:
                    project_dir = matches[0]
                    scraper_path = project_dir / "generated_scraper.py"
                    if not scraper_path.exists():
                        scraper_path = project_dir / "test_flow.py"

        if not scraper_path.exists():
            return {
                "project_id": project_id,
                "status": "error",
                "drift_rate": 1.0,
                "stable_selectors": [],
                "failing_selectors": [],
                "message": f"Scraper script not found for project: {project_id}."
            }
            
        # 3. Run the scraper script using ScriptTester
        success, output = ScriptTester.run_test(scraper_path, project_dir, wizard_mode=True)
        
        actual_items = []
        if success:
            output_file = project_dir / "output" / "data.json"
            if output_file.exists():
                try:
                    with open(output_file, "r", encoding="utf-8") as f:
                        actual_items = json.load(f)
                except Exception as e:
                    success = False
                    output = f"Failed to parse scraper output data.json: {e}\n{output}"

        if not success:
            return {
                "project_id": project_id,
                "status": "drift_detected",
                "drift_rate": 1.0,
                "stable_selectors": [],
                "failing_selectors": ["all"],
                "message": f"Scraper execution failed.\nOutput: {output}"
            }
            
        # 4. Calculate Parity & Drift
        if not expected_items:
            drift_rate = 0.0 if actual_items else 1.0
            return {
                "project_id": project_id,
                "status": "success" if drift_rate < 0.2 else "drift_detected",
                "drift_rate": drift_rate,
                "stable_selectors": ["all"] if actual_items else [],
                "failing_selectors": [] if actual_items else ["all"],
                "message": "Validation complete. No baseline extracts found; evaluated based on output existence."
            }
            
        stable_selectors = set()
        failing_selectors = set()
        
        total_keys = 0
        drifted_keys = 0
        
        for exp_item, act_item in zip(expected_items, actual_items):
            for k, v in exp_item.items():
                total_keys += 1
                if k not in act_item or act_item[k] is None or act_item[k] == "":
                    drifted_keys += 1
                    failing_selectors.add(k)
                elif act_item[k] != v:
                    drifted_keys += 1
                    failing_selectors.add(k)
                else:
                    stable_selectors.add(k)
                    
        # Account for length mismatch
        len_diff = abs(len(expected_items) - len(actual_items))
        if len_diff > 0:
            avg_keys_per_item = len(expected_items[0].keys()) if expected_items else 1
            drifted_keys += len_diff * avg_keys_per_item
            total_keys += len_diff * avg_keys_per_item
            if len(expected_items) > len(actual_items) and expected_items:
                for k in expected_items[0].keys():
                    failing_selectors.add(k)
            
        drift_rate = drifted_keys / total_keys if total_keys > 0 else 0.0
        
        stable_selectors = list(stable_selectors - failing_selectors)
        failing_selectors = list(failing_selectors)
        
        return {
            "project_id": project_id,
            "status": "success" if drift_rate < 0.2 else "drift_detected",
            "drift_rate": drift_rate,
            "stable_selectors": stable_selectors,
            "failing_selectors": failing_selectors,
            "message": f"Validation complete. Drift rate is {drift_rate:.2%}."
        }

    def _load_recording_baseline(self, path: Path) -> List[Dict[str, Any]]:
        baseline = []
        if not path.exists():
            return baseline
            
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line)
                if event.get("type") == "extract":
                    baseline.append(event.get("data"))
        return baseline

