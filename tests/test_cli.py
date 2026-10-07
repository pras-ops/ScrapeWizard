import pytest
from typer.testing import CliRunner
from scrapewizard.cli.main import app

runner = CliRunner()

def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ScrapeWizard" in result.output

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scrape" in result.output
