import ast
from pathlib import Path
from scrapewizard.core.logging import log

class ScriptValidator:
    """
    Validates Python scripts for syntax correctness.
    """
    
    @classmethod
    def validate(cls, script_path: Path) -> bool:
        """Check for syntax errors."""
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
            return True
        except SyntaxError as e:
            log(f"Syntax validation failed for {script_path}: {e}", level="error")
            return False
        except Exception as e:
            log(f"Validation failed: {e}", level="error")
            return False
