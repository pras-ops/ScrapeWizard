from pathlib import Path
from typing import Callable, Optional, List
from scrapewizard.healing.classifier import ErrorClassifier
from scrapewizard.llm.repair import RepairAgent
from scrapewizard.core.logging import log

class RepairLoop:
    """
    Manages the test-fail-repair cycle with optional column-specific hints.
    """
    def __init__(self, project_dir: Path, wizard_mode: bool = False):
        self.project_dir = project_dir
        self.agent = RepairAgent(project_dir)
        self.max_attempts = 2
        self.wizard_mode = wizard_mode

    def run(
        self, 
        script_path: Path, 
        test_runner: Callable[[], tuple[bool, str]],
        column_hints: Optional[List[str]] = None
    ) -> bool:
        """
        Run the repair loop.
        test_runner should return (success: bool, error_msg: str)
        column_hints: optional list of column names that need fixing
        """
        attempts = 0
        
        while attempts <= self.max_attempts:
            if attempts > 0:
                if not self.wizard_mode:
                    log(f"Repair attempt {attempts}/{self.max_attempts}...")
            
            # Run the test
            success, output = test_runner()
            
            if success:
                if not self.wizard_mode:
                    log("Verification successful!" if attempts > 0 else "Test passed.")
                return True
            
            # Failed
            if not self.wizard_mode:
                log(f"Test failed. Output: {output[:300]}...")
            if attempts == self.max_attempts:
                if not self.wizard_mode:
                    log("Max repair attempts reached.", level="error")
                return False
                
            error_type = ErrorClassifier.classify(output)
            if not self.wizard_mode:
                log(f"Detected error type: {error_type}")
            
            if not ErrorClassifier.is_recoverable(error_type):
                if not self.wizard_mode:
                    log("Error is likely not recoverable via code changes.", level="warning")
            
            # Build context with column hints if provided
            context = ""
            if column_hints:
                context = f"USER FEEDBACK: The following columns have incorrect/missing data: {', '.join(column_hints)}. Please fix the selectors for these fields."
                if not self.wizard_mode:
                    log(f"Including user feedback about columns: {column_hints}")
            
            # Call repair
            try:
                self.agent.repair(script_path, output, context=context)
            except Exception as e:
                import traceback
                log(f"Repair agent failed: {e}", level="error")
                log(f"Repair Traceback: {traceback.format_exc()}", level="debug")
                return False
                
            attempts += 1
            
        return False
