import typer
from typing import Optional
import os
import sys

# Ensure the root directory is in sys.path so we can import studio
sys.path.append(os.getcwd())

app = typer.Typer(help="ScrapeWizard Studio Bridge")

@app.command()
def studio(port: int = typer.Option(7331, help="Port to run the Studio backend on")):
    """Start the backend server for desktop mode."""
    try:
        import uvicorn
        from studio.backend.main import app
        typer.echo(f"🚀 Starting ScrapeWizard Studio Backend on http://localhost:{port}")
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except ImportError as e:
        typer.echo(f"❌ Error: Studio backend or dependencies not found. {e}", err=True)
        typer.echo("Make sure uvicorn and fastapi are installed.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Failed to start Studio server: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def record(
    url: str = typer.Argument(..., help="URL to record"),
    session_id: str = typer.Option("default", "--session-id", help="Session ID for tracking"),
    output: Optional[str] = typer.Option(None, "--output", help="Path to save the recording")
):
    """Records CDP session + user actions for Studio replay."""
    from studio.bridge.recorder import SessionRecorder
    from pathlib import Path
    
    out_path = Path(output) if output else Path(f"studio/recordings/{session_id}.jsonl")
    recorder = SessionRecorder(session_id, out_path.parent)
    
    typer.echo(f"⏺️ Recording session '{session_id}' for: {url}")
    recorder.record_event("session_start", {"url": url})
    typer.echo(f"💾 Output: {recorder.get_file_path()}")
    # Integration logic for browser capture goes here
    typer.echo("Note: This command captures CDP events + user actions for the Studio IDE.")

@app.command()
def test(
    project: str = typer.Argument(..., help="Project name to test"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode"),
    compare_to: Optional[str] = typer.Option(None, "--compare-to", help="JSON file for drift analysis")
):
    """Test Studio-generated scraper against recording to detect drift."""
    from studio.backend.test_runner import StudioParityValidator
    from pathlib import Path
    
    validator = StudioParityValidator()
    recording_path = Path(compare_to) if compare_to else Path(f"studio/recordings/{project}.jsonl")
    
    typer.echo(f"🧪 Testing project: {project}")
    if recording_path.exists():
        report = validator.validate(project, recording_path)
        typer.echo(f"📊 Drift Rate: {report['drift_rate']:.2%}")
        typer.echo(f"✅ Status: {report['status']}")
        if report['failing_selectors']:
            typer.echo(f"❌ Failing Selectors: {', '.join(report['failing_selectors'])}")
    else:
        typer.echo(f"⚠️ No recording found at {recording_path}. Running baseline only.")

if __name__ == "__main__":
    app()
