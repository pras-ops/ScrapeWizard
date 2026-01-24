import os
import subprocess
import sys
import traceback
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
            log(f"Running execution: {script_path.name} (timeout: {timeout}s)")
        
        try:
            # Cleanup stale output to prevent false positives
            output_file = cwd / "output" / "data.json"
            if output_file.exists():
                try:
                    os.remove(output_file)
                except Exception:
                    pass

            # Ensure scrapewizard_runtime is in PYTHONPATH
            # It's located in the workspace root
            workspace_root = Path(__file__).parent.parent.parent
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            if python_path:
                python_path = str(workspace_root) + os.pathsep + python_path
            else:
                python_path = str(workspace_root)
            env["PYTHONPATH"] = python_path

            # Run with python -u (unbuffered)
            result = subprocess.run(
                [sys.executable, "-u", str(script_path.name)],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            output = f"{result.stdout}\n{result.stderr}"
            
            if result.returncode == 0:
                # Basic check: did it crash?
                # Deeper check: did it produce output?
                output_file = cwd / "output" / "data.json"
                if output_file.exists() and output_file.stat().st_size > 2:
                    return True, output
                else:
                    return False, f"Script ran but produced no data.\nOutput:\n{output}"
            else:
                return False, f"Process exited with code {result.returncode}.\nOutput:\n{output}"
                
        except subprocess.TimeoutExpired:
            log(f"Execution timed out after {timeout}s", level="warning")
            return False, f"Execution timed out ({timeout}s)."
        except PermissionError as e:
            log(f"Permission denied executing script: {e}", level="error")
            return False, f"Permission denied executing script: {e}"
        except Exception as e:
            log(f"Unexpected execution error: {traceback.format_exc()}", level="error")
            return False, f"Unexpected execution error: {e}"
