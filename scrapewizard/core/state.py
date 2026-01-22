from enum import Enum, auto

class State(Enum):
    INIT = "INIT"
    LOGIN = "LOGIN"  # Legacy, kep for compatibility
    GUIDED_ACCESS = "GUIDED_ACCESS"
    RECON = "RECON"
    INTERACTIVE_SOLVE = "INTERACTIVE_SOLVE"
    LLM_ANALYSIS = "LLM_ANALYSIS"
    USER_CONFIG = "USER_CONFIG"
    CODEGEN = "CODEGEN"
    TEST = "TEST"
    REPAIR = "REPAIR"
    APPROVED = "APPROVED"
    FINAL_RUN = "FINAL_RUN"
    DONE = "DONE"
    FAILED = "FAILED"

class TransitionError(Exception):
    pass
