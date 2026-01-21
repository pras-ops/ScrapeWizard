import typer
import sys
import os
import shutil
import platform
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.core.orchestrator import Orchestrator
from scrapewizard.core.logging import log, Logger

console = Console(width=100) # Force width for better rendering in snapshots

def list_projects():
    """List all local scraper projects."""
    projects = ProjectManager.list_projects()
    
    if not projects:
        rprint("[yellow]No projects found.[/yellow]")
        return

    rprint(f"\n[bold cyan]Found {len(projects)} projects:[/bold cyan]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Project ID", style="dim")
    table.add_column("URL")
    table.add_column("Last Modified")
    table.add_column("Status")

    for p in projects:
        session = ProjectManager.load_project(str(p))
        if session:
            mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            status = session.get("state", "unknown")
            url = session.get("url", "unknown")
            # Truncate URL if too long
            if len(url) > 40:
                url = url[:37] + "..."
            table.add_row(p.name, url, mtime, status)
        else:
            table.add_row(p.name, "[red]Invalid Session[/red]", "-", "-")
    
    console.print(table)

def clean(
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    """Clean up old projects."""
    projects = ProjectManager.list_projects()
    if not projects:
        rprint("[yellow]Nothing to clean.[/yellow]")
        return
        
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete {len(projects)} projects?")
        if not confirm:
            rprint("[yellow]Aborted.[/yellow]")
            return

    for p in projects:
        try:
            shutil.rmtree(p)
            rprint(f"[dim]Deleted {p.name}[/dim]")
        except Exception as e:
            rprint(f"[red]Failed to delete {p.name}: {e}[/red]")
    
    rprint("[green]Cleanup complete.[/green]")

def doctor():
    """Check environment health."""
    rprint("[bold cyan]Checking ScrapeWizard environment...[/bold cyan]")
    from scrapewizard.core.config import ConfigManager
    
    rprint(f"• OS: {platform.system()} {platform.release()}")
    rprint(f"• Python: {sys.version.split()[0]}")
    
    config_ok = ConfigManager.check_setup()
    rprint(f"• Configuration: {'[green]OK[/green]' if config_ok else '[red]MISSING (Run setup)[/red]'}")
    
    playwright = shutil.which("playwright")
    rprint(f"• Playwright CLI: {'[green]OK[/green]' if playwright else '[red]MISSING[/red]'}")
    
    projects_dir = ProjectManager.PROJECTS_ROOT
    rprint(f"• Projects Directory: {projects_dir} ({'[green]Ready[/green]' if projects_dir.exists() else '[yellow]Not initialized[/yellow]'})")
    
    # Check LLM connectivity if config exists
    if config_ok:
        try:
            from scrapewizard.llm.client import LLMClient
            client = LLMClient()
            # Simple check or just mention it
            rprint("• LLM Client: [green]Initialized[/green]")
        except Exception as e:
            rprint(f"• LLM Client: [red]Error ({e})[/red]")
    
    rprint("\n[bold green]System check complete.[/bold green]")

def resume(project_id: str = typer.Argument(..., help="The ID of the project to resume")):
    """Resume an existing project."""
    projects_root = ProjectManager.PROJECTS_ROOT
    project_dir = projects_root / project_id
    
    if not project_dir.exists():
        rprint(f"[red]Error: Project '{project_id}' not found.[/red]")
        rprint(f"Looking in: {projects_root}")
        list_projects()
        raise typer.Exit(code=1)
        
    rprint(f"[bold cyan]Resuming project:[/bold cyan] {project_id}")
    
    try:
        # Setup logging for the orchestrator
        Logger.setup_logging(log_dir=project_dir, verbose=False)
        
        orchestrator = Orchestrator(project_dir)
        orchestrator.run()
    except Exception as e:
        rprint(f"[red]Resume failed: {e}[/red]")
        raise typer.Exit(code=1)
