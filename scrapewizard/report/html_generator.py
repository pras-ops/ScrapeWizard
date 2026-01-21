import json
import jinja2
from pathlib import Path
from datetime import datetime
from typing import Dict
from scrapewizard.core.logging import log

class ReportGenerator:
    """
    Generates an HTML report from scraping results.
    """
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates")
        )

    def generate(self):
        """Generate report.html."""
        log("Generating HTML report...")
        
        # Gather data
        data_file = self.project_dir / "output" / "data.json"
        items = []
        if data_file.exists():
            with open(data_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        
        # Mock stats for MVP if not tracked elsewhere
        stats = {
            "rows_extracted": len(items),
            "duration_seconds": 0, # Placeholder
            "error_count": 0
        }
        
        # Meta
        meta = {
            "url": "Unknown",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # Try to get URL from session
        session_file = self.project_dir / "session.json"
        if session_file.exists():
            with open(session_file) as f:
                sess = json.load(f)
                meta["url"] = sess.get("url", "Unknown")

        # Render
        template = self.env.get_template("report.html.jinja")
        html = template.render(
            meta=meta,
            stats=stats,
            sample_data=items[:10] # Top 10 rows
        )
        
        out_path = self.project_dir / "report.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        log(f"Report generated at {out_path}")
