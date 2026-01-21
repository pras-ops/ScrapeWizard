class ErrorClassifier:
    """
    Classifies runtime errors to determine repair strategy.
    """
    @classmethod
    def classify(cls, error_msg: str) -> str:
        error_msg = error_msg.lower()
        
        if "timeouterror" in error_msg:
            return "timeout_error"
        if "syntaxerror" in error_msg or "indentationerror" in error_msg:
            return "syntax_error"
        if "waiting for selector" in error_msg or "element not found" in error_msg:
            return "selector_error"
        if "network" in error_msg or "connection refused" in error_msg:
            return "network_error"
            
        return "general_error"

    @classmethod
    def is_recoverable(cls, error_type: str) -> bool:
        # Network errors might be transient, but code errors are fixable
        return error_type in ["syntax_error", "selector_error", "timeout_error"]
