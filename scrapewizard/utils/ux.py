import sys
from typing import List, Dict, Any, Optional
from yaspin import yaspin
from rich.console import Console

console = Console()

class UX:
    """
    Centralized UX handler for the streamlined CLI.
    Wraps Yaspin for spinners and consolidates Rich output.
    """

    @staticmethod
    def spinner(text: str):
        """Returns a configured yaspin spinner."""
        return yaspin(text=text, color="cyan", spinner="dots")

    @staticmethod
    def print_success(message: str):
        console.print(f"[green]✓ {message}[/green]")

    @staticmethod
    def print_error(message: str):
        console.print(f"[red]✗ {message}[/red]")

    @staticmethod
    def print_warning(message: str):
        console.print(f"[yellow]⚠️  {message}[/yellow]")

    @staticmethod
    def auto_select_format(row_count: int, has_nested_data: bool = False) -> str:
        """
        Smartly decide the best output format.
        - JSON for deeply nested data.
        - CSV for massive datasets (speed).
        - Excel for standard usage (< 50k rows).
        """
        if has_nested_data:
            return "json"
        
        if row_count > 50000:
            return "csv"
            
        return "xlsx"

    @staticmethod
    def analyze_pagination_signal(analysis: Dict[str, Any]) -> str:
        """
        Determine pagination strategy based on analysis.
        Returns 'first_page' (default) or 'all_pages' if significant pagination found,
        but implementation depends on user mode.
        """
        # Placeholder for deeper logic, currently defaults safe
        return "first_page"
