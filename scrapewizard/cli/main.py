import typer
from scrapewizard.cli.commands import setup, scrape, utils
from scrapewizard.core.logging import Logger

app = typer.Typer(
    name="scrapewizard",
    help="Agentic Web Scraper Builder",
    add_completion=False
)

# Register commands
app.command()(setup.setup)
app.command()(scrape.scrape)
app.command(name="list")(utils.list_projects)
app.command()(utils.clean)
app.command()(utils.doctor)
app.command()(utils.resume)

VERSION = "MVP-1.0.0"

@app.command()
def version():
    """Show the ScrapeWizard version."""
    typer.echo(f"ScrapeWizard {VERSION}")

def version_callback(value: bool):
    if value:
        typer.echo(f"ScrapeWizard {VERSION}")
        raise typer.Exit()

@app.callback()
def main(
    version: bool = typer.Option(None, "--version", callback=version_callback, is_eager=True),
):
    """
    ScrapeWizard CLI - Automate your scraping tasks.
    """
    pass

if __name__ == "__main__":
    app()
