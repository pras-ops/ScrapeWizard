import typer
import json
from InquirerPy import inquirer
from scrapewizard.core.config import ConfigManager
from scrapewizard.core.logging import log

def setup(
    provider: str = typer.Option(None, help="LLM Provider (openai, anthropic, etc.)"),
    api_key: str = typer.Option(None, help="API Key for the provider"),
    model: str = typer.Option(None, help="Model name (e.g. gpt-4-turbo)"),
    use_proxy: bool = typer.Option(False, help="Enable proxy configuration")
):
    """
    Configure ScrapeWizard global settings.
    """
    log("Running setup...")
    
    current_config = ConfigManager.load_config()
    
    # Interactive mode if arguments are missing
    if not provider:
        provider = inquirer.select(
            message="Select LLM Provider:",
            choices=["openai", "anthropic", "openrouter", "local"],
            default=current_config.get("provider", "openai")
        ).execute()

    if not api_key:
        api_key = inquirer.text(
            message="Enter API Key:",
            default=current_config.get("api_key", ""),
            validate=lambda result: len(result) > 0 or "API Key cannot be empty"
        ).execute()

    if not model:
        default_models = {
            "openai": "gpt-4-turbo",
            "anthropic": "claude-3-opus-20240229",
            "openrouter": "google/gemini-pro",
            "local": "llama3"
        }
        model = inquirer.text(
            message="Enter Model Name:",
            default=current_config.get("model", default_models.get(provider, ""))
        ).execute()

    # Save Config
    new_config = {
        "provider": provider,
        "api_key": api_key,
        "model": model
    }
    ConfigManager.save_config(new_config)
    log("Configuration saved successfully.")

    # Proxy Setup
    if use_proxy or inquirer.confirm(message="Configure Proxy?", default=False).execute():
        proxy_url = inquirer.text(message="Proxy URL (http://user:pass@host:port):").execute()
        if proxy_url:
            ConfigManager.save_proxy({"url": proxy_url})
            log("Proxy settings saved.")
