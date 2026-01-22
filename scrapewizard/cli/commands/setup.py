import typer
import json
from typing import Dict, Any, List, Optional, Tuple
from InquirerPy import inquirer
from scrapewizard.core.config import ConfigManager
from scrapewizard.core.logging import log

def setup(
    provider: Optional[str] = typer.Option(None, help="LLM Provider (openai, anthropic, openrouter, local)"),
    api_key: Optional[str] = typer.Option(None, help="API Key for the provider"),
    model: Optional[str] = typer.Option(None, help="Model name (e.g. gpt-4-turbo)"),
    use_proxy: bool = typer.Option(False, help="Enable proxy configuration")
) -> None:
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
        # Check if we already have one
        existing_key = current_config.get("api_key", "")
        key_masked = f"{existing_key[:4]}...{existing_key[-4:]}" if len(existing_key) > 8 else "********" if existing_key else ""
        
        api_key = inquirer.text(
            message=f"Enter API Key (Current: {key_masked}):",
            default=existing_key,
            validate=lambda result: len(result) > 0 or "API Key cannot be empty"
        ).execute()

    if not model:
        default_models = {
            "openai": "gpt-4-turbo",
            "anthropic": "claude-3-5-sonnet-20240620",
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

def auth(
    api_key: str = typer.Argument(..., help="The LLM API key to store securely")
) -> None:
    """
    Securely store your LLM API key in the system keyring.
    """
    try:
        config = ConfigManager.load_config()
        config["api_key"] = api_key
        ConfigManager.save_config(config)
        log("API Key stored securely in keyring.")
    except Exception as e:
        log(f"Failed to save API key: {e}", level="error")
        raise typer.Exit(code=1)
