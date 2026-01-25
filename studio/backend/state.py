from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class StudioState(Enum):
    INIT = "INIT"
    NAVIGATION = "NAVIGATION"
    VISUAL_SCHEMA = "VISUAL_SCHEMA"
    DOM_BIND = "DOM_BIND"
    PATTERN_INFERENCE = "PATTERN_INFERENCE"
    VALIDATION = "VALIDATION"
    HARDENING = "HARDENING"
    CODEGEN = "CODEGEN"
    EXPORT = "EXPORT"
    FAILED = "FAILED"

class FieldDefinition(BaseModel):
    name: str
    type: str
    selector: Optional[str] = None
    icon: Optional[str] = None

class StudioProject(BaseModel):
    project_id: str
    url: str
    state: StudioState = StudioState.INIT
    schema_fields: List[FieldDefinition] = []
    current_selector: Optional[str] = None
    extraction_results: List[Dict[str, Any]] = []
