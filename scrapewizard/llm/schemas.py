from typing import Any
from scrapewizard.llm.routing import LLMTask

UNDERSTANDING_SCHEMA = {
    "type": "object",
    "properties": {
        "scraping_possible": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "recommended_browser_mode": {"type": "string", "enum": ["headless", "headed"]},
        "reason": {"type": "string"},
        "available_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "selector_guess": {"type": "string"}
                },
                "required": ["name", "description", "selector_guess"]
            }
        },
        "pagination": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string", "enum": ["next_button", "url_param", "none"]},
                "next_button_selector": {"type": ["string", "null"]}
            },
            "required": ["strategy", "next_button_selector"]
        }
    },
    "required": ["scraping_possible", "confidence", "recommended_browser_mode", "reason", "available_fields", "pagination"]
}

HEAL_SCHEMA = {
    "type": "object",
    "properties": {
        "healed_selector": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string"}
    },
    "required": ["healed_selector", "confidence", "reasoning"]
}

STEP_NAME_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"}
    },
    "required": ["name"]
}

TASK_SCHEMAS = {
    LLMTask.UNDERSTAND: UNDERSTANDING_SCHEMA,
    LLMTask.HEAL_SELECTOR: HEAL_SCHEMA,
    LLMTask.STEP_NAME: STEP_NAME_SCHEMA
}

def validate_schema(data: Any, schema: dict) -> bool:
    """A lightweight JSON schema validator to avoid external dependencies."""
    if not isinstance(data, dict):
        return False
        
    # Check required fields
    for req in schema.get("required", []):
        if req not in data:
            return False
            
    # Validate types of defined properties
    properties = schema.get("properties", {})
    for key, val in data.items():
        if key in properties:
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            
            # Check if expected_type is a list of types (e.g. ["string", "null"])
            allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
            
            type_match = False
            for t in allowed_types:
                if t == "boolean" and isinstance(val, bool):
                    type_match = True
                elif t == "number" and isinstance(val, (int, float)) and not isinstance(val, bool):
                    type_match = True
                elif t == "string" and isinstance(val, str):
                    type_match = True
                elif t == "array" and isinstance(val, list):
                    # For simple items validation
                    if "items" in prop_schema and isinstance(prop_schema["items"], dict):
                        item_schema = prop_schema["items"]
                        if not all(validate_schema(item, item_schema) for item in val):
                            return False
                    type_match = True
                elif t == "object" and isinstance(val, dict):
                    if not validate_schema(val, prop_schema):
                        return False
                    type_match = True
                elif t == "null" and val is None:
                    type_match = True
                    
            if not type_match:
                return False
                
    return True

