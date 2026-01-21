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
    def ask_login_required() -> bool:
        """Step 3: Ask if sites needs login."""
        return inquirer.select(
            message="Does this site require login or navigation to reach data?",
            choices=[
                Choice(name="No (Public Site)", value=False),
                Choice(name="Yes (Login / Click-through)", value=True)
            ],
            default=False
        ).execute()

    @staticmethod
    def confirm_browser_mode(recommended: str, reason: str) -> str:
        """Ask user to confirm browser mode (headless vs headed)."""
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
    def prompt_credentials() -> Dict[str, str]:
        username = inquirer.text(message="Username:").execute()
        password = inquirer.secret(message="Password:").execute()
        return {"username": username, "password": password}

    @staticmethod
    def ask_fields(available_fields: List[Dict]) -> List[str]:
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
        """Step 6.2: Pagination."""
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
        """Step 6.3: Output Format."""
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
    async def wait_for_solve(reason: str = "A CAPTCHA or blocking screen was detected.") -> bool:
        """Pause execution and let user solve a blocker in the headed browser."""
        console.print(f"\n[bold red]🛑 ACTION REQUIRED: {reason}[/bold red]")
        console.print("[yellow]Please solve the CAPTCHA or bypass the blocker in the browser window.[/yellow]")
        console.print("[dim]- ScrapeWizard is waiting for you...[/dim]")
        
        return await inquirer.confirm(
            message="Have you solved the blocker and reached the data?",
            default=True
        ).execute_async()

    @staticmethod
    def override_llm_hallucination(reason: str) -> bool:
        console.print(f"\n[bold yellow]⚠️  LLM thinks scraping may NOT be feasible.[/bold yellow]")
        console.print(f"[dim]Reason: {reason}[/dim]")
        return inquirer.confirm(message="Continue anyway?", default=False).execute()

    @staticmethod
    def show_data_preview(data: List[Dict], max_rows: int = 5) -> None:
        """
        Display a rich table preview of scraped data.
        """
        if not data:
            console.print("[yellow]No data to preview.[/yellow]")
            return
            
        # Build table
        table = Table(title="📊 Data Preview (First {} rows)".format(min(len(data), max_rows)))
        
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
                    val_str = val_str[:37] + "..."
                values.append(val_str)
            table.add_row(*values)
        
        console.print(table)
        console.print(f"\n[dim]Total rows: {len(data)}[/dim]")

    @staticmethod
    def review_data_quality(data: List[Dict]) -> Tuple[str, Optional[List[str]]]:
        """
        Let user review data and choose action:
        - approve: proceed with full run
        - fix_columns: specify columns that need fixing
        - abort: cancel everything
        
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
                Choice("fix_columns", "🔧 Some columns need fixing - let me select"),
                Choice("retry", "🔄 Re-generate the scraper from scratch"),
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
        """Simple approve prompt (legacy, use review_data_quality for richer flow)."""
        return inquirer.confirm(message="Proceed with full scraping?").execute()
