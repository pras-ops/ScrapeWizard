from enum import Enum
from scrapewizard.core.config import ConfigManager

class LLMTask(Enum):
    STEP_NAME = "step_name"           # ~50 tokens out, structured
    UNDERSTAND = "understand"         # ~500 tokens out, structured JSON
    HEAL_SELECTOR = "heal_selector"   # ~200 tokens out, structured JSON
    CODEGEN = "codegen"               # ~2000 tokens out, free-form Python
    REPAIR = "repair"                 # ~2000 tokens out, free-form Python


class RoutingPolicy:
    """Decides which provider + model to use for a given task."""

    def route(self, task: LLMTask, config: dict, force_cloud: bool = False) -> tuple[str, str]:
        """Returns (provider_id, model_name).

        Policy:
        - If provider is not "local" (e.g. "openai", "anthropic", "openrouter"), use that directly.
        - If provider is "local":
          - If config 'offline_only' is True, run everything locally.
          - If the task is UNDERSTAND, HEAL_SELECTOR, or STEP_NAME (and not force_cloud), run locally.
          - If the task is CODEGEN or REPAIR (or force_cloud is True), look for a cloud API key.
            If a cloud key is found, fall back to cloud. Otherwise, run locally.
        """
        provider = config.get("provider", "openai")

        if provider != "local":
            return provider, config.get("model", "gpt-4-turbo")

        local_model = config.get("local_model", "qwen2.5-coder:3b")

        # Hard switch: offline only
        if config.get("offline_only", False):
            return "local", local_model

        # Only fall back for codegen, repair, or force_cloud
        if not force_cloud and task not in (LLMTask.CODEGEN, LLMTask.REPAIR):
            return "local", local_model

        # Try to find a cloud provider that has an API key stored in the keyring
        # First preference: OpenAI
        openai_key = ConfigManager.get_api_key("openai")
        if openai_key:
            fallback_model = config.get("model") if config.get("provider") == "openai" else "gpt-4-turbo"
            return "openai", fallback_model

        # Second preference: Anthropic
        anthropic_key = ConfigManager.get_api_key("anthropic")
        if anthropic_key:
            fallback_model = config.get("model") if config.get("provider") == "anthropic" else "claude-3-5-sonnet"
            return "anthropic", fallback_model

        # Third preference: OpenRouter
        openrouter_key = ConfigManager.get_api_key("openrouter")
        if openrouter_key:
            fallback_model = config.get("model") if config.get("provider") == "openrouter" else "gpt-4-turbo"
            return "openrouter", fallback_model

        # No cloud keys available, stay local
        return "local", local_model
