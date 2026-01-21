import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio

from scrapewizard.core.state import State
from scrapewizard.core.project_manager import ProjectManager
from scrapewizard.core.logging import log
from scrapewizard.core.config import ConfigManager

from scrapewizard.interactive.ui import UI
from scrapewizard.recon.browser import BrowserManager
from scrapewizard.recon.scanner import Scanner
from scrapewizard.recon.dom_analyzer import DOMAnalyzer
from scrapewizard.recon.pagination import PaginationDetector
from scrapewizard.recon.tech_fingerprint import TechFingerprinter

from scrapewizard.llm.understanding import UnderstandingAgent
from scrapewizard.llm.codegen import CodeGenerator
from scrapewizard.llm.repair import RepairAgent

from scrapewizard.healing.repair_loop import RepairLoop
from scrapewizard.runtime.tester import ScriptTester

class Orchestrator:
    """
    Main controller for the scraping workflow.
    Uses synchronous flow with isolated async blocks for browser operations.
    """

    def __init__(self, project_dir: Path, ci_mode: bool = False):
        self.project_dir = Path(project_dir)
        self.ci_mode = ci_mode
        self.session = ProjectManager.load_project(str(self.project_dir))
        if not self.session:
            raise ValueError(f"Invalid project directory: {project_dir}")
        
    def run(self):
        """Main execution loop (synchronous)."""
        log("Starting Orchestrator loop...")
        if self.ci_mode:
            log("CI Mode enabled: Automatic defaults will be used.")
            
        while self.session["state"] != State.DONE.value and self.session["state"] != State.FAILED.value:
            current_state = self.session["state"]
            log(f"Current State: {current_state}")
            
            try:
                if current_state == State.INIT.value:
                    self._handle_init()
                elif current_state == State.LOGIN.value:
                    self._handle_login()
                elif current_state == State.RECON.value:
                    self._handle_recon()
                elif current_state == State.LLM_ANALYSIS.value:
                    self._handle_llm_analysis()
                elif current_state == State.USER_CONFIG.value:
                    self._handle_user_config()
                elif current_state == State.CODEGEN.value:
                    self._handle_codegen()
                elif current_state == State.TEST.value:
                    self._handle_test()
                elif current_state == State.REPAIR.value:
                    self._handle_repair()
                elif current_state == State.INTERACTIVE_SOLVE.value:
                    self._handle_interactive_solve()
                elif current_state == State.APPROVED.value:
                    self._handle_final_run()
                else:
                    log(f"State {current_state} not handled.", level="error")
                    break
                    
                ProjectManager.save_state(self.project_dir, self.session)
                
            except Exception as e:
                log(f"Critical error: {e}", level="error")
                import traceback
                traceback.print_exc()
                self._transition_to(State.FAILED)
                ProjectManager.save_state(self.project_dir, self.session)
                raise

    def _transition_to(self, new_state: State):
        log(f"Transitioning: {self.session['state']} -> {new_state.value}")
        self.session["state"] = new_state.value

    def _handle_init(self):
        """Step 3: Ask user if login is required."""
        if self.ci_mode:
            login_required = False # Default to non-interactive
        else:
            login_required = UI.ask_login_required()
            
        interaction_log = {"login_required": login_required, "steps": []}
        
        with open(self.project_dir / "interaction.json", "w", encoding="utf-8") as f:
            json.dump(interaction_log, f, indent=2)
            
        if login_required:
            self._transition_to(State.LOGIN)
        else:
            self._transition_to(State.RECON)

    def _handle_login(self):
        """Manual login via visible browser."""
        if self.ci_mode:
            log("CI Mode: Bypassing manual login. Proceeding to RECON.", level="warning")
            self._transition_to(State.RECON)
            return

        log("Starting interactive login...")
        
        async def do_login():
            browser = BrowserManager(headless=False)
            await browser.start()
            try:
                url = self.session["url"]
                print(f"Please log in to {url} in the browser window.")
                print("Navigate to the target page you want to scrape.")
                await browser.navigate(url)
                
                input("Press ENTER after you have logged in and reached the target page...")
                
                cookies = await browser.get_cookies()
                final_url = browser.page.url
                
                with open(self.project_dir / "cookies.json", "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                
                self.session["url"] = final_url
                
            finally:
                await browser.close()
        
        asyncio.run(do_login())
        
        # UI prompts AFTER async block
        if UI.ask_save_credentials():
            creds = UI.prompt_credentials()
            with open(self.project_dir / ".env", "w", encoding="utf-8") as f:
                f.write(f"USERNAME={creds['username']}\n")
                f.write(f"PASSWORD={creds['password']}\n")
            
        self._transition_to(State.RECON)

    def _handle_recon(self):
        """Run browser reconnaissance."""
        log("Starting Reconnaissance...")
        
        cookies = None
        cookie_file = self.project_dir / "cookies.json"
        if cookie_file.exists():
            with open(cookie_file) as f:
                cookies = json.load(f)

        async def do_recon():
            browser = BrowserManager(headless=True)
            await browser.start()
            try:
                if cookies:
                    await browser.inject_cookies(cookies)
                    
                await browser.navigate(self.session["url"])
                
                # 1. Run Behavioral Scan
                scanner = Scanner(browser.page)
                scan_profile = await scanner.scan(self.session["url"])
                
                # Save Scan Profile
                with open(self.project_dir / "scan_profile.json", "w", encoding="utf-8") as f:
                    json.dump(scan_profile, f, indent=2)
                
                html = await browser.get_content()
                
                await browser.take_screenshot(self.project_dir / "debug_recon.png")
                
                # Analyze
                analyzer = DOMAnalyzer(html)
                analysis = analyzer.analyze()
                
                pg_detector = PaginationDetector(analyzer.soup, self.session["url"])
                analysis["pagination"] = pg_detector.detect()
                
                tech_detector = TechFingerprinter(analyzer.soup)
                analysis["meta"] = {
                    "url": self.session["url"],
                    "title": await browser.page.title(),
                    "detected_tech": tech_detector.detect()
                }
                analysis["interaction_used"] = False
                
                with open(self.project_dir / "analysis_snapshot.json", "w", encoding="utf-8") as f:
                    json.dump(analysis, f, indent=2)
                    
            finally:
                await browser.close()
        
        asyncio.run(do_recon())
        
        # Check for CAPTCHA
        with open(self.project_dir / "scan_profile.json", "r") as f:
            profile = json.load(f)
            
        if profile.get("tech_stack", {}).get("anti_bot", {}).get("captcha") and not self.ci_mode:
            self._transition_to(State.INTERACTIVE_SOLVE)
        else:
            self._transition_to(State.LLM_ANALYSIS)

    def _handle_interactive_solve(self):
        """HITL: Let user solve CAPTCHA/Blocker manually."""
        log("Entering INTERACTIVE_SOLVE state...")
        
        async def do_solve():
            browser = BrowserManager(headless=False)
            await browser.start()
            try:
                await browser.navigate(self.session["url"])
                # Wait for user
                if await UI.wait_for_solve(reason="CAPTCHA or blocking screen detected."):
                    # Capture current state after solve
                    log("User confirmed solve. Re-scanning page state...")
                    scanner = Scanner(browser.page)
                    scan_profile = await scanner.scan(browser.page.url)
                    
                    with open(self.project_dir / "scan_profile.json", "w", encoding="utf-8") as f:
                        json.dump(scan_profile, f, indent=2)
                        
                    html = await browser.get_content()
                    analyzer = DOMAnalyzer(html)
                    analysis = analyzer.analyze()
                    
                    with open(self.project_dir / "analysis_snapshot.json", "w", encoding="utf-8") as f:
                        json.dump(analysis, f, indent=2)
                        
                    # Capture interaction: user solved captcha
                    interaction = {"captcha_solved_manually": True, "final_url": browser.page.url}
                    with open(self.project_dir / "interaction.json", "w", encoding="utf-8") as f:
                        json.dump(interaction, f, indent=2)
                        
                    # Also capture cookies to bypass future CAPTCHAs
                    cookies = await browser.get_cookies()
                    with open(self.project_dir / "cookies.json", "w", encoding="utf-8") as f:
                        json.dump(cookies, f, indent=2)
                        
                    log("Cookies saved for generated script.")
                else:
                    log("User cancelled solve.", level="warning")
                    self._transition_to(State.FAILED)
                    return False
                return True
            finally:
                await browser.close()
                
        if asyncio.run(do_solve()):
            self._transition_to(State.LLM_ANALYSIS)

    def _handle_llm_analysis(self):
        """Call LLM for understanding."""
        agent = UnderstandingAgent(self.project_dir)
        
        with open(self.project_dir / "analysis_snapshot.json", "r") as f:
            snapshot = json.load(f)
            
        interaction = None
        if (self.project_dir / "interaction.json").exists():
             with open(self.project_dir / "interaction.json", "r") as f:
                interaction = json.load(f)
        
        scan_profile = None
        if (self.project_dir / "scan_profile.json").exists():
            with open(self.project_dir / "scan_profile.json", "r") as f:
                scan_profile = json.load(f)
        
        understanding = agent.analyze(snapshot, scan_profile, interaction)
        
        if self.ci_mode:
            if not understanding.get("scraping_possible") or understanding.get("confidence", 0) < 0.5:
                log(f"CI Mode Aborted: {understanding.get('reason', 'Ambiguous UI detected')}", level="error")
                self._transition_to(State.FAILED)
                return
        else:
            if not understanding.get("scraping_possible", False):
                if not UI.override_llm_hallucination(understanding.get("reason", "Unknown")):
                    self._transition_to(State.FAILED)
                    return

        self._transition_to(State.USER_CONFIG)

    def _handle_user_config(self):
        """Get user selections for fields, pagination, format."""
        with open(self.project_dir / "llm_understanding.json", "r") as f:
            understanding = json.load(f)
            
        if self.ci_mode:
            # Smart defaults for CI
            fields = [f.get('name') for f in understanding.get("available_fields", [])][:5] # Limit to 5
            if not fields:
                fields = ["item_title", "item_price"] # Generic fallback
            pagination = "first_page"
            fmt = "json"
            browser_mode = understanding.get("recommended_browser_mode", "headless")
            log(f"CI Mode: Using defaults - Fields: {fields}, Pagination: {pagination}, Format: {fmt}, Browser Mode: {browser_mode}")
        else:
            fields = UI.ask_fields(understanding.get("available_fields", []))
            pagination = UI.ask_pagination()
            fmt = UI.ask_format()
            browser_mode = UI.confirm_browser_mode(
                understanding.get("recommended_browser_mode", "headless"),
                understanding.get("reason", "No reason provided")
            )
        
        config = {
            "fields": fields,
            "pagination": pagination,
            "format": fmt,
            "browser_mode": browser_mode
        }
        
        with open(self.project_dir / "run_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
        self._transition_to(State.CODEGEN)

    def _handle_codegen(self):
        """Generate scraper code via LLM."""
        agent = CodeGenerator(self.project_dir)
        
        with open(self.project_dir / "analysis_snapshot.json") as f: 
            snapshot = json.load(f)
        with open(self.project_dir / "llm_understanding.json") as f: 
            understanding = json.load(f)
        with open(self.project_dir / "run_config.json") as f: 
            run_config = json.load(f)
        scan_profile = None
        if (self.project_dir / "scan_profile.json").exists():
             with open(self.project_dir / "scan_profile.json", "r") as f:
                 scan_profile = json.load(f)

        interaction = None
        if (self.project_dir / "interaction.json").exists():
             with open(self.project_dir / "interaction.json") as f: 
                 interaction = json.load(f)

        agent.generate(snapshot, understanding, run_config, scan_profile, interaction)
        self._transition_to(State.TEST)

    def _handle_test(self):
        """Run auto-test on generated scraper with rich data preview."""
        log("Running auto-test on generated scraper...")
        
        success, output = ScriptTester.run_test(
            self.project_dir / "generated_scraper.py",
            self.project_dir,
            timeout=120
        )
        
        if success:
            log("Test Passed!")
            
            # Load and preview the data
            data = self._load_output_data()
            
            if self.ci_mode:
                if data:
                    log(f"CI Mode: Test passed with {len(data)} rows. Auto-approving.")
                    self._transition_to(State.APPROVED)
                else:
                    log("CI Mode: Test passed but no data returned. Failing.", level="error")
                    self._transition_to(State.FAILED)
                return

            if data:
                # Use rich review flow
                action, bad_cols = UI.review_data_quality(data)
                
                if action == "approve":
                    self._transition_to(State.APPROVED)
                elif action == "fix_columns":
                    # Store columns to fix and trigger repair
                    self.session["fix_columns"] = bad_cols
                    log(f"User flagged columns for repair: {bad_cols}")
                    self._transition_to(State.REPAIR)
                elif action == "retry":
                    # Go back to codegen
                    log("User requested regeneration.")
                    self._transition_to(State.CODEGEN)
                else:  # abort
                    log("User aborted.")
                    self._transition_to(State.DONE)
            else:
                # No data but script ran - simple approval
                if UI.approve_run():
                    self._transition_to(State.APPROVED)
                else:
                    self._transition_to(State.DONE)
        else:
            log(f"Test Failed. Output: {output[:200]}...")
            self._transition_to(State.REPAIR)

    def _load_output_data(self):
        """Load output/data.json if exists."""
        data_file = self.project_dir / "output" / "data.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return None
        return None

    def _handle_repair(self):
        """Self-healing repair loop with optional column-specific hints."""
        loop = RepairLoop(self.project_dir)
        
        # Check if user flagged specific columns
        fix_columns = self.session.get("fix_columns", None)
        if fix_columns:
            log(f"Attempting to fix columns: {fix_columns}")
            # We'll pass this hint to repair agent
            self.session.pop("fix_columns", None)
        
        def runner():
            return ScriptTester.run_test(
                self.project_dir / "generated_scraper.py",
                self.project_dir,
                timeout=120
            )
        
        # Run repair with column hints if available
        fixed = loop.run(
            self.project_dir / "generated_scraper.py", 
            runner,
            column_hints=fix_columns
        )
        
        if fixed:
            if self.ci_mode:
                log("CI Mode: Repair successful. Auto-approving.")
                self._transition_to(State.APPROVED)
                return

            # Show data again after fix
            data = self._load_output_data()
            if data:
                action, bad_cols = UI.review_data_quality(data)
                if action == "approve":
                    self._transition_to(State.APPROVED)
                elif action == "fix_columns":
                    self.session["fix_columns"] = bad_cols
                    log("User requested another fix round.")
                    # Stay in REPAIR but we've exhausted attempts
                    self._transition_to(State.FAILED)
                elif action == "retry":
                    log("User requested regeneration.")
                    self._transition_to(State.CODEGEN)
                else:
                    log("User aborted.")
                    self._transition_to(State.DONE)
            else:
                if UI.approve_run():
                    self._transition_to(State.APPROVED)
                else:
                    self._transition_to(State.DONE)
        else:
            log("Repair failed. Proceeding to DONE (failed state).")
            self._transition_to(State.FAILED)

    def _handle_final_run(self):
        """Final scraping run and bundle output."""
        log("Starting Final Run...")
        
        # Final run gets a much longer timeout (10 minutes)
        success, output = ScriptTester.run_test(
            self.project_dir / "generated_scraper.py",
            self.project_dir,
            timeout=600 
        )
        
        if success:
            # Bundle all project files into output folder
            self._bundle_output()
            log(f"Final run complete. All files bundled in {self.project_dir}/output")
            self._transition_to(State.DONE)
        else:
            log("Final run failed.")
            self._transition_to(State.FAILED)

    def _bundle_output(self):
        """
        Copy all relevant project files into the output folder for portability.
        User requested: script, logs, JSON configs, .env all in one place.
        """
        import shutil
        output_dir = self.project_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Files to copy
        files_to_bundle = [
            "generated_scraper.py",
            "analysis_snapshot.json",
            "llm_understanding.json",
            "run_config.json",
            "session.json",
            "interaction.json",
            "cookies.json",
            ".env"
        ]
        
        for fname in files_to_bundle:
            src = self.project_dir / fname
            if src.exists():
                shutil.copy2(src, output_dir / fname)
        
        # Copy logs folder
        logs_src = self.project_dir / "logs"
        logs_dst = output_dir / "logs"
        if logs_src.exists():
            if logs_dst.exists():
                shutil.rmtree(logs_dst)
            shutil.copytree(logs_src, logs_dst)
        
        # Copy llm_logs folder
        llm_logs_src = self.project_dir / "llm_logs"
        llm_logs_dst = output_dir / "llm_logs"
        if llm_logs_src.exists():
            if llm_logs_dst.exists():
                shutil.rmtree(llm_logs_dst)
            shutil.copytree(llm_logs_src, llm_logs_dst)
        
        log("Project files bundled into output folder.")
