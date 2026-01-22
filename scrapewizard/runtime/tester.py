import subprocess
import sys
from pathlib import Path
from typing import Tuple, Optional
from scrapewizard.core.logging import log

class ScriptTester:
    """
    Executes the generated script and captures output.
    """
    
    @classmethod
    def run_test(cls, script_path: Path, cwd: Path, timeout: int = 60, wizard_mode: bool = False) -> Tuple[bool, str]:
        """
        Run the script in a subprocess.
        Returns (success, output/error_message).
        """
        if not wizard_mode:
            log(f"Running execution: {script_path} (timeout: {timeout}s)")
        
        try:
            # Run with python -u (unbuffered)
            result = subprocess.run(
                [sys.executable, "-u", str(script_path.name)],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout + "\n" + result.stderr
            
            if result.returncode == 0:
                # Basic check: did it crash?
                # Deeper check: did it produce output?
                output_file = cwd / "output" / "data.json"
                if output_file.exists() and output_file.stat().st_size > 2:
                    return True, output
                else:
                    return False, f"Script ran but produced no data.\nOutput:\n{output}"
            else:
                return False, output
                
        except subprocess.TimeoutExpired:
            return False, f"Execution timed out ({timeout}s)."
        except Exception as e:
            return False, f"Execution failed to start: {e}"
