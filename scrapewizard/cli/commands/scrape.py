import typer
import sys
from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.core.orchestrator import Orchestrator
from scrapewizard.core.logging import log, Logger
from scrapewizard.core.config import ConfigManager

def scrape(
    url: str = typer.Option(..., help="Target URL to scrape"),
    headless: bool = typer.Option(True, help="Run browser in headless mode"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    ci: bool = typer.Option(False, "--ci", help="Run in non-interactive CI mode (auto-accept defaults)"),
    expert: bool = typer.Option(False, "--expert", help="Expert mode - show all technical details")
):
    """
    Start a new scraping session for a URL.
    """
    # Check setup
    if not ConfigManager.check_setup():
        log("ScrapeWizard is not configured. Please run 'scrapewizard setup' first.", level="error")
        raise typer.Exit(code=1)

    # Setup logging
    # We don't have project dir yet, so just console log first
    Logger.setup_logging(verbose=verbose)
    
    # Wizard mode is default (unless expert or ci flag)
    wizard_mode = not expert and not ci

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
        orchestrator = Orchestrator(project_dir, ci_mode=ci, wizard_mode=wizard_mode)
        orchestrator.run()
        
    except Exception as e:
        log(f"Scrape failed: {e}", level="error")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)
