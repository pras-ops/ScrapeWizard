import asyncio
import json
import typer
from pathlib import Path
from scrapewizard.engine.recorder import InteractiveRecorder
from scrapewizard.engine.sandbox import SandboxRunner

app = typer.Typer(help="Self-healing test automation engine commands")

def async_command(f):
    """Decorator to run async Typer commands synchronously."""
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@app.command(name="record")
@async_command
async def record(
    url: str = typer.Option(..., "--url", "-u", help="Target URL to start recording from"),
    output: str = typer.Option("flow.json", "--output", "-o", help="Path to save the generated flow.json"),
    screenshots: str = typer.Option("screenshots", "--screenshots", "-s", help="Directory to save crop screenshots")
):
    """
    Open a headed browser to record user interactions on a page.
    Saves the flow steps and element fingerprints to a flow.json file.
    """
    typer.echo(f"Starting interactive recording on {url}...")
    recorder = InteractiveRecorder(output_path=output, screenshots_dir=screenshots, headless=False)
    await recorder.start(url)
    typer.echo(f"Successfully saved flow recording to {output}")

@app.command(name="test")
@async_command
async def test(
    flow_path: str = typer.Argument(..., help="Path to the flow.json file to execute"),
    artifacts: str = typer.Option(None, "--artifacts", "-a", help="Directory to save run artifacts"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run the browser in headless or headed mode")
):
    """
    Run an automated headless sandbox execution of the recorded flow.json.
    Validates console/network errors, visual diffs, and accessibility violations.
    """
    flow_file = Path(flow_path)
    if not flow_file.exists():
        typer.echo(f"Error: flow file not found at {flow_path}", err=True)
        raise typer.Exit(code=1)
        
    try:
        with open(flow_file, "r", encoding="utf-8") as f:
            flow_data = json.load(f)
    except Exception as e:
        typer.echo(f"Error: failed to parse JSON in {flow_path}: {e}", err=True)
        raise typer.Exit(code=1)
        
    # Construct test definition from flow data directly
    from scrapewizard.engine.test_generator import TestGenerator
    generator = TestGenerator(flow_path)
    test_def = generator.generate()
    
    typer.echo(f"Running sandbox execution for {flow_path}...")
    runner = SandboxRunner(artifacts_dir=artifacts, headless=headless)
    result = await runner.run(test_def)
    
    # Print results
    typer.echo(f"\nExecution finished in {result.duration_ms} ms. Status: {result.status.upper()}")
    typer.echo(f"Artifacts saved to: {result.artifacts_dir}\n")
    
    for idx, step in enumerate(result.step_results):
        status_symbol = "✅" if step.status == "passed" else "❌"
        typer.echo(f" {status_symbol} Step {idx + 1}: {step.step_name} - {step.status.upper()} ({step.duration_ms} ms)")
        if step.error_message:
            typer.echo(f"    Error: {step.error_message}")
        if step.console_errors:
            typer.echo(f"    Console Errors ({len(step.console_errors)}):")
            for err in step.console_errors:
                typer.echo(f"      - {err}")
        if step.network_errors:
            typer.echo(f"    Network Failures ({len(step.network_errors)}):")
            for err in step.network_errors:
                typer.echo(f"      - {err}")
        if step.a11y_violations:
            typer.echo(f"    A11y Violations ({len(step.a11y_violations)}):")
            for violation in step.a11y_violations:
                typer.echo(f"      - [{violation['impact']}] {violation['id']}: {violation['help']}")
                
    if result.status != "passed":
        typer.echo("\n❌ Run FAILED.")
        raise typer.Exit(code=1)
    else:
        typer.echo("\n✅ Run PASSED.")
        raise typer.Exit(code=0)
