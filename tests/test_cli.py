import pytest
from typer.testing import CliRunner
from scrapewizard.cli.main import app
from scrapewizard.cli.commands.bridge import app as bridge_app

runner = CliRunner()

def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "ScrapeWizard" in result.output

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scrape" in result.output
    # Note: studio is no longer in main app help due to core freeze
    # It lives in the bridge app

def test_bridge_studio_help():
    result = runner.invoke(bridge_app, ["studio", "--help"])
    assert result.exit_code == 0
    assert "--port" in result.output

def test_bridge_record_help():
    result = runner.invoke(bridge_app, ["record", "--help"])
    assert result.exit_code == 0
    assert "URL" in result.output

def test_bridge_test_help():
    result = runner.invoke(bridge_app, ["test", "--help"])
    assert result.exit_code == 0
    assert "PROJECT" in result.output
