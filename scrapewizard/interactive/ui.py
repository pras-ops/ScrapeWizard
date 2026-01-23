from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import List, Dict, Any, Tuple, Optional

console = Console()

class UI:
    """
    Handles all interactive user prompts with rich display.
    """
    

    @staticmethod
    def confirm_browser_mode(recommended: str, reason: str, wizard_mode: bool = False) -> str:
        """Ask user to confirm browser mode (headless vs headed)."""
        # Wizard mode: auto-decide, no prompt
        if wizard_mode:
            return recommended
        
        # Expert mode: show prompt
        console.print(f"\n[bold cyan]🔍 Browser Mode Analysis[/bold cyan]")
        color = "yellow" if recommended == "headed" else "green"
        console.print(f"Recommended: [{color}]{recommended.upper()}[/{color}]")
        console.print(f"[dim]Reason: {reason}[/dim]")
        
        return inquirer.select(
            message="Confirm browser mode:",
            choices=[
                Choice("headless", "Headless (Invisible, Faster)"),
                Choice("headed", "Headed (Visible, Better Compatibility)")
            ],
            default=recommended
        ).execute()

    @staticmethod
    def ask_save_credentials() -> bool:
        return inquirer.confirm(message="Save username/password for the generated script?").execute()

    @staticmethod
    def ask_access_mode(recommendation: str = "automatic", reason: str = "") -> str:
        """
        Step 3: Unified Access Mode Selection.
        Replaces 'Does this site require login?' with a smarter choice.
        """
        console.print(f"\n[bold cyan]🔐 Access Mode Recommendation[/bold cyan]")
        
        if recommendation == "guided":
            if "Hostile" in reason:
                # Wizard Mode: No choice, explanation only
                console.print(f"[bold red]🛡️  Bot Protection Detected[/bold red]")
                console.print(f"[yellow]This website uses active bot defenses ({reason}).[/yellow]")
                console.print("[white]ScrapeWizard will open a real browser so you can navigate normally.[/white]")
                console.print("[dim]Headless mode is disabled to prevent blocking.[/dim]")
                return inquirer.select(
                    message="Proceed with Guided Access?",
                    choices=[Choice(name="Open Browser (Guided)", value="guided")],
                    default="guided"
                ).execute()
            
            console.print(f"[yellow]⚠️  System recommends: GUIDED ACCESS (Headed)[/yellow]")
            console.print(f"[dim]Reason: {reason}[/dim]")
            default_val = "guided"
        else:
            console.print(f"[green]✅ System recommends: AUTOMATIC (Headless)[/green]")
            console.print(f"[dim]Reason: {reason or 'Site appears static and safe.'}[/dim]")
            default_val = "automatic"

        console.print()
        
        return inquirer.select(
            message="How should ScrapeWizard reach the target data?",
            choices=[
                Choice(name="Automatic (Headless, fastest)", value="automatic"),
                Choice(name="Guided (Open real browser, I will navigate manually)", value="guided")
            ],
            default=default_val
        ).execute()

    @staticmethod
    def prompt_credentials() -> Dict[str, str]:
        username = inquirer.text(message="Username:").execute()
        password = inquirer.secret(message="Password:").execute()
        return {"username": username, "password": password}

    @staticmethod
    def show_smart_preview(data: List[Dict[str, Any]]) -> bool:
        """
        Consolidated preview for Zero-Click mode.
        Shows the table and a brief summary.
        Returns: True if critical issues were found, False otherwise.
        """
        if not data:
            console.print("[yellow]⚠️  No data extracted during test run.[/yellow]")
            return True

        # Show table
        UI.show_data_preview(data, max_rows=5)
        
        # Check for quality issues
        columns = list(data[0].keys())
        null_counts = {col: sum(1 for row in data if not row.get(col)) for col in columns}
        bad_cols = [col for col, count in null_counts.items() if count > len(data) * 0.8] # >80% null
        
        if bad_cols:
            console.print(f"\n[bold yellow]⚠️  Warning: High missing data in columns: {', '.join(bad_cols)}[/bold yellow]")
            return True
            
        return False
        

    @staticmethod
    def ask_fields_wizard(available_fields: List[Dict[str, Any]], suggested_fields: List[Dict[str, Any]], interactive: bool = False) -> List[str]:
        """
        Wizard mode.
        - Zero-Click (default): Auto-accept suggestions.
        - Interactive: Ask user.
        """
        suggested_names = [f["name"] for f in suggested_fields]
        
        if not suggested_fields:
            console.print("\n[yellow]⚠️  No clear repeating patterns found. Switching to manual selection.[/yellow]")
            return UI.ask_fields(available_fields)

        console.print(f"\n[green]✓ Found {len(suggested_names)} data fields:[/green] {', '.join(suggested_names)}")
        
        if not interactive:
            return suggested_names
        
        # Interactive mode only
        choice = inquirer.select(
            message="Use these suggested fields?",
            choices=[
                Choice(value="yes", name="✅ Yes, these look correct"),
                Choice(value="no", name="❌ No, let me pick manually"),
                Choice(value="retry", name="🔍 Look again (Deep Scan)")
            ],
            default="yes"
        ).execute()
        
        if choice == "yes":
            return suggested_names
        elif choice == "retry":
            return "retry"
        
        return UI.ask_fields(available_fields)

    @staticmethod
    def ask_fields(available_fields: List[Dict[str, Any]]) -> List[str]:
        """
        Step 6.1: Select fields to scrape.
        Uses checkbox for MULTI-SELECT. All fields are pre-selected by default.
        """
        if not available_fields:
            console.print("[yellow]No fields detected. Will use default extraction.[/yellow]")
            return []
        
        console.print("\n[bold cyan]Available Fields Detected:[/bold cyan]")
        for i, f in enumerate(available_fields, 1):
            name = f.get('name', 'unknown')
            desc = f.get('description', '')
            selector = f.get('selector_guess', 'auto')
            console.print(f"  {i}. [green]{name}[/green] - {desc} [dim](selector: {selector})[/dim]")
        print()
        
        # Ask user: select all or choose specific?
        select_mode = inquirer.select(
            message="Field selection mode:",
            choices=[
                Choice("all", "Select ALL fields"),
                Choice("choose", "Choose specific fields")
            ],
            default="all"
        ).execute()
        
        if select_mode == "all":
            all_names = [f.get('name', 'unknown') for f in available_fields]
            console.print(f"[green]Selected all {len(all_names)} field(s)[/green]")
            return all_names
            
        # Manual selection
        choices = []
        for f in available_fields:
            name = f.get('name', 'unknown')
            desc = f.get('description', '')
            choices.append(Choice(name=f"{name} ({desc})", value=name))
            
        selected = inquirer.checkbox(
            message="Select fields to scrape (use SPACE to toggle, ENTER to confirm):",
            choices=choices,
            validate=lambda result: len(result) > 0 or "Select at least one field.",
            instruction="(Press SPACE to select/deselect, ENTER to confirm)"
        ).execute()
        
        console.print(f"[green]Selected {len(selected)} field(s)[/green]")
        return selected

    @staticmethod
    def ask_pagination() -> str:
        """Step 6.3: Pagination."""
        return inquirer.select(
            message="Pagination Strategy:",
            choices=[
                Choice("all_pages", "All Pages (scrape everything)"),
                Choice("first_page", "First Page Only (quick test)"),
                Choice("limit_5", "Limit to 5 Pages")
            ]
        ).execute()

    @staticmethod
    def ask_format() -> str:
        """Step 6.4: Output Format."""
        return inquirer.select(
            message="Output Format:",
            choices=[
                Choice("json", "JSON"),
                Choice("csv", "CSV"),
                Choice("xlsx", "Excel"),
                Choice("all", "All formats")
            ]
        ).execute()

    @staticmethod
    async def wait_for_solve(reason: str = "") -> bool:
        """Pause execution for Page Verification."""
        console.print(f"\n[bold yellow]⚠️  Page Verification Required[/bold yellow]")
        console.print("[white]ScrapeWizard has reached a page and needs your confirmation before continuing.[/white]")
        console.print("\n[dim]Please check the browser window and confirm:[/dim]")
        console.print("  1. Is this the [bold]correct page[/bold] with the data you want?")
        console.print("  2. Does it match your requirements (table, list, profile, etc.)?")
        console.print("\n[yellow]If YES:[/yellow] Type [bold green]Y[/bold green] to continue.")
        console.print("[yellow]If NO (Blocker/Wrong Page):[/yellow]")
        console.print("  • Solve any CAPTCHA/Login/Popup in the browser.")
        console.print("  • Navigate to the correct page if needed.")
        console.print("  • Then return here and type [bold green]Y[/bold green].")
        
        return await inquirer.confirm(
            message="Ready to scrape this view?",
            default=True
        ).execute_async()

    @staticmethod
    def override_llm_hallucination(reason: str) -> bool:
        console.print(f"\n[bold yellow]⚠️  LLM thinks scraping may NOT be feasible.[/bold yellow]")
        console.print(f"[dim]Reason: {reason}[/dim]")
        return inquirer.confirm(message="Continue anyway?", default=False).execute()

    @staticmethod
    def show_data_preview(data: List[Dict[str, Any]], max_rows: int = 5) -> None:
        """
        Display a rich table preview of scraped data.
        """
        if not data:
            console.print("[yellow]No data to preview.[/yellow]")
            return
            
        # Build table
        table = Table(title=f"📊 Data Preview (First {min(len(data), max_rows)} rows)")
        
        # Get columns from first row
        columns = list(data[0].keys())
        for col in columns:
            table.add_column(col, style="cyan", overflow="fold")
        
        # Add rows
        for row in data[:max_rows]:
            values = []
            for col in columns:
                val = row.get(col, "")
                # Truncate long values
                val_str = str(val) if val else "[dim]null[/dim]"
                if len(val_str) > 40:
                    val_str = f"{val_str[:37]}..."
                values.append(val_str)
            table.add_row(*values)
        
        console.print(table)
        console.print(f"\n[dim]Total rows: {len(data)}[/dim]")

    @staticmethod
    def review_data_quality(data: List[Dict[str, Any]]) -> Tuple[str, Optional[List[str]]]:
        """
        Let user review data and choose action.
        Returns: (action, list of problematic columns or None)
        """
        if not data:
            return ("abort", None)
        
        # Show preview first
        UI.show_data_preview(data)
        
        # Check for null/empty columns
        columns = list(data[0].keys())
        problematic = []
        for col in columns:
            null_count = sum(1 for row in data if not row.get(col))
            if null_count > len(data) * 0.5:  # More than 50% null
                problematic.append(col)
        
        if problematic:
            console.print(f"\n[yellow]⚠️  Potential issues detected in columns: {', '.join(problematic)}[/yellow]")
        
        # Ask user
        action = inquirer.select(
            message="How does the data look?",
            choices=[
                Choice("approve", "✅ Looks good - proceed with full scraping"),
                Choice("fix_columns", "🩺 Auto-fix: Let AI repair specific columns"),
                Choice("guided", "🖐️  Manual: Re-run in Guided Mode (Fix in browser)"),
                Choice("retry", "🔄 Re-generate everything (Full retry)"),
                Choice("abort", "❌ Cancel and exit")
            ]
        ).execute()
        
        if action == "fix_columns":
            # Let user select which columns are problematic
            col_choices = [Choice(name=col, value=col) for col in columns]
            bad_cols = inquirer.checkbox(
                message="Select columns that have incorrect data:",
                choices=col_choices
            ).execute()
            return ("fix_columns", bad_cols)
        
        return (action, None)

    @staticmethod
    def approve_run() -> bool:
        """Simple approve prompt."""
        return inquirer.confirm(message="Proceed with full scraping?").execute()

    @staticmethod
    def ask_test_failure_action(error_msg: str) -> str:
        """Handle the case where a test run fails."""
        console.print(f"\n[bold red]❌ Test Execution Failed[/bold red]")
        console.print(f"[dim]Error: {error_msg[:200]}...[/dim]\n")
        
        return inquirer.select(
            message="What would you like to do?",
            choices=[
                Choice("repair", "🩺 Attempt Auto-Repair (AI-driven)"),
                Choice("config", "📋 Back to Configuration (Change fields/mode)"),
                Choice("edit", "📝 Manual Fix (Open code in editor)"),
                Choice("abort", "❌ Abort and exit")
            ],
            default="repair"
        ).execute()

    @staticmethod
    def ask_repair_failure_action() -> str:
        """Handle the case where auto-repair fails."""
        console.print(f"\n[bold yellow]⚠️  Auto-Repair was unable to fix the issue.[/bold yellow]")
        
        return inquirer.select(
            message="How would you like to proceed?",
            choices=[
                Choice("config", "📋 Back to Configuration"),
                Choice("edit", "📝 Manual Fix"),
                Choice("abort", "❌ Abort and exit")
            ],
            default="config"
        ).execute()
