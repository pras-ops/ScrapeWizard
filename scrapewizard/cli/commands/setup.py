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

    if provider == "local":
        import shutil
        from scrapewizard.llm.local_runtime import LocalRuntime
        
        ollama_installed = shutil.which("ollama") is not None
        if not ollama_installed:
            print("⚠️ [yellow]Warning: 'ollama' executable not found on system PATH. Please ensure Ollama is installed.[/yellow]")
            
        local_base_url = current_config.get("local_base_url", "http://localhost:11434")
        if not model:
            local_base_url = inquirer.text(
                message="Enter Ollama Base URL:",
                default=local_base_url
            ).execute()
        
        runtime = LocalRuntime(base_url=local_base_url)
        daemon_status = runtime.check_daemon()
        
        if not daemon_status.running and not model:
            print("❌ [red]Error: Ollama daemon is not running at configured URL.[/red]")
            if not inquirer.confirm(message="Ollama daemon is down. Proceed anyway?", default=False).execute():
                log("Setup aborted.")
                return
                
        # Detect hardware
        hw = runtime.detect_hardware()
        if not model:
            print(f"🖥️ [cyan]Hardware detected:[/cyan] {hw['ram_gb']} GB RAM, GPU: {hw['gpu_name']}")
            print(f"📦 Suggested performance tier: [green]{hw['tier'].upper()}[/green]")
        
        recommended = runtime.recommend_model(hw['tier'])
        
        selected_model = model
        if not selected_model:
            installed = runtime.list_models()
            if installed:
                print("Installed models:")
                for m in installed:
                    print(f"  • {m}")
            else:
                print("No models found in Ollama.")
                
            choices = installed.copy()
            if recommended not in choices:
                choices.append(recommended)
            choices.append("Other (enter custom name)")
            
            selected_model = inquirer.select(
                message="Select Ollama model:",
                choices=choices,
                default=recommended if recommended in choices else (installed[0] if installed else choices[0])
            ).execute()
            
            if selected_model == "Other (enter custom name)":
                selected_model = inquirer.text(
                    message="Enter custom model name:",
                    default=recommended
                ).execute()
                
            if selected_model not in installed:
                if inquirer.confirm(message=f"Model '{selected_model}' is not downloaded. Pull it now?", default=True).execute():
                    print(f"Downloading '{selected_model}' via Ollama. Please wait...")
                    
                    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        DownloadColumn(),
                    ) as progress:
                        task = progress.add_task(f"Pulling {selected_model}...", total=100)
                        
                        def callback(data):
                            status = data.get("status", "")
                            total = data.get("total", 0)
                            completed = data.get("completed", 0)
                            if total > 0:
                                progress.update(task, completed=completed, total=total, description=f"Pulling {selected_model}: {status}")
                            else:
                                progress.update(task, description=f"Pulling {selected_model}: {status}")
                                
                        success = runtime.pull_model(selected_model, callback)
                        if success:
                            print(f"✅ Model '{selected_model}' pulled successfully.")
                        else:
                            print(f"❌ Failed to pull model '{selected_model}'.")
                            
        # Probe model latency
        if daemon_status.running and not model:
            print("Probing model response latency...")
            probe_res = runtime.probe(selected_model)
            if probe_res.success:
                print(f"✅ Connection successful! Probe latency: [green]{probe_res.latency}s[/green]")
            else:
                print(f"⚠️ Probe check failed: {probe_res.error}")
                
        offline_only = current_config.get("offline_only", False)
        if not model:
            offline_only = inquirer.confirm(message="Enable offline-only mode (disable all cloud fallbacks)?", default=False).execute()
            
        new_config = {
            "provider": "local",
            "model": selected_model,
            "local_base_url": local_base_url,
            "local_model": selected_model,
            "local_tier": hw['tier'],
            "offline_only": offline_only
        }
        ConfigManager.save_config(new_config)
        log("Configuration saved successfully.")

    else:
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
                "openrouter": "google/gemini-pro"
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
