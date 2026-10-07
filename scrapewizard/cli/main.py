import sys
import typer
from typer.core import TyperGroup
from scrapewizard.cli.commands import setup, scrape, utils, recipe
from scrapewizard.core.logging import Logger

# Ensure Windows/CMD/PowerShell console supports UTF-8/emoji output without crashing
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class UrlFirstGroup(TyperGroup):
    """Lets `scrapewizard <url>` work as shorthand for `scrapewizard get <url>`."""

    def parse_args(self, ctx, args):
        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args = ["get", *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="scrapewizard",
    cls=UrlFirstGroup,
    help="Get data from web pages. Start with: scrapewizard <url>",
    add_completion=False
)

# Register commands
app.command(name="get")(recipe.get)
app.command(name="run")(recipe.run)
app.command()(setup.setup)
app.command(name="login")(setup.auth)
app.command(name="build")(scrape.scrape)
app.command(name="list")(utils.list_projects)
app.command()(utils.clean)
app.command()(utils.doctor)
app.command()(utils.resume)

VERSION = "1.2.0"

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
