import typer
import sys
from typing import Optional, Any, Dict, List
from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.core.orchestrator import Orchestrator
from scrapewizard.core.logging import log, Logger
from scrapewizard.core.config import ConfigManager
from rich.console import Console

console = Console()

def scrape(
    url: str = typer.Option(None, "--url", help="Target URL to scrape"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    ci: bool = typer.Option(False, "--ci", help="Run in non-interactive CI mode (auto-accept defaults)"),
    expert: bool = typer.Option(False, "--expert", help="Expert mode - show all technical details"),
    guided_tour: bool = typer.Option(False, "--guided-tour", help="Guided tour mode - step-by-step narration")
):
    """
    Start a new scraping session for a URL.
    """
    # Check setup
    if not ConfigManager.check_setup():
        log("ScrapeWizard is not configured. Please run 'scrapewizard setup' first.", level="error")
        raise typer.Exit(code=1)

    # Setup logging
    # Wizard mode is default (unless expert or ci flag)
    wizard_mode = not expert and not ci

    if guided_tour:
        wizard_mode = True
        url = url or "https://books.toscrape.com" # Default tutorial URL
        log(f"Starting Guided Tour for: {url}")
    
    if not url and not guided_tour:
        console.print("[bold red]Error:[/bold red] You must provide a --url to scrape, or use --guided-tour.")
        raise typer.Exit(code=1)

    if url:
        try:
            url = ConfigManager.validate_url(url)
        except ValueError as e:
            log(str(e), level="error")
            raise typer.Exit(code=1)

    if not wizard_mode:
        log(f"Initializing project for {url}...")
    
    try:
        session = ProjectManager.create_project(url)
        project_id = session["project_id"]
        project_dir = session["project_dir"]
        
        # Re-setup logging to include project logs
        Logger.setup_logging(log_dir=project_dir, verbose=verbose)
        
        if not wizard_mode:
            log(f"Project created: {project_id}")
            log(f"Project directory: {project_dir}")

        # Start Orchestrator
        orchestrator = Orchestrator(project_dir, ci_mode=ci, wizard_mode=wizard_mode, guided_tour=guided_tour)
        orchestrator.run()
        
    except KeyboardInterrupt:
        log("Scrape interrupted by user.", level="warning")
        raise typer.Exit(code=0)
    except Exception as e:
        import traceback
        log(f"Scrape failed: {e}", level="error")
        log(f"Fatal Traceback: {traceback.format_exc()}", level="debug")
        if verbose:
            traceback.print_exc()
        raise typer.Exit(code=1)
