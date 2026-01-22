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

    def __init__(self, project_dir: Path, ci_mode: bool = False, wizard_mode: bool = True):
        self.project_dir = Path(project_dir)
        self.ci_mode = ci_mode
        self.wizard_mode = wizard_mode  # Default: friendly UI
        self._working_shown = False  # Track working message
        self.session = ProjectManager.load_project(str(self.project_dir))
        if not self.session:
            raise ValueError(f"Invalid project directory: {project_dir}")
        
    def run(self):
        """Main execution loop (synchronous)."""
        if not self.wizard_mode:
            log("Starting Orchestrator loop...")
            if self.ci_mode:
                log("CI Mode enabled: Automatic defaults will be used.")
            
        while self.session["state"] != State.DONE.value and self.session["state"] != State.FAILED.value:
            current_state = self.session["state"]
            if not self.wizard_mode:
                log(f"Current State: {current_state}")
            
            try:
                if current_state == State.INIT.value:
                    self._handle_init()
                elif current_state == State.LOGIN.value or current_state == State.GUIDED_ACCESS.value:
                    self._handle_guided_access()
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
                    if not self.wizard_mode:
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
        if not self.wizard_mode:
            log(f"Transitioning: {self.session['state']} -> {new_state.value}")
        self.session["state"] = new_state.value

    def _handle_init(self):
        """Step 3: Analyze complexity -> Ask Access Mode."""
        # Wizard mode: Show friendly welcome
        if self.wizard_mode:
            print("\n🧙 ScrapeWizard\n")
            print("Opening the website…\n")
        
        if self.ci_mode:
            log("CI Mode: Skipping complexity check, defaulting to Automatic.")
            self._transition_to(State.RECON)
            return

        # 1. Run Pre-Scan in Stealth Probe mode (headed, not guided)
        if not self.wizard_mode:
            log("Running Pre-Scan to determine site complexity...")
        
        if self.wizard_mode:
            print("Checking the website…\n")
        
        # Pre-Scan uses HEADED mode to trigger real bot defenses (Akamai, PerimeterX, etc.)
        # This is a silent probe - no user interaction required
        async def do_prescan():
            browser = BrowserManager(headless=False, wizard_mode=self.wizard_mode)  # Stealth Probe
            await browser.start()
            try:
                scanner = Scanner(browser.page)
                return await scanner.scan(self.session["url"], wizard_mode=self.wizard_mode)
            finally:
                await browser.close()

        profile = asyncio.run(do_prescan())
        
        rec = profile.get("access_recommendation", "automatic")
        score = profile.get("complexity_score", 0)
        reasons = ", ".join(profile.get("complexity_reasons", []))
        
        if not self.wizard_mode:
            log(f"Complexity Analysis: Score={score}, Rec={rec}, Reasons={reasons}")

        # 2. Ask User (or auto-decide in wizard mode)
        if self.wizard_mode:
            # Wizard mode: auto-decide, no question
            mode = rec  # Use scanner recommendation directly
            if mode == "guided":
                print("\n🌐 This website blocks bots, so we'll open a real browser.\n")
                print("Please use the browser like you normally would:")
                print("  • Log in if needed")
                print("  • Search or filter to what you want")
                print("  • Scroll until the items you want are visible\n")
                print("When the screen shows exactly what you want scraped,")
                print("come back here and press Enter.\n")
        else:
            # Expert mode: ask user
            mode = UI.ask_access_mode(recommendation=rec, reason=reasons)
            
        interaction_log = {"access_mode": mode, "complexity_score": score, "steps": []}
        with open(self.project_dir / "interaction.json", "w", encoding="utf-8") as f:
            json.dump(interaction_log, f, indent=2)
            
        if mode == "guided":
            self._transition_to(State.GUIDED_ACCESS)
        else:
            self._transition_to(State.RECON)

    def _handle_guided_access(self):
        """Guided Access via visible browser (Replaces Login)."""
        if self.ci_mode:
            log("CI Mode: Bypassing guided access. Proceeding to RECON.", level="warning")
            self._transition_to(State.RECON)
            return

        if not self.wizard_mode:
            log("Starting Guided Access Phase...")
        
        async def do_login():
            browser = BrowserManager(headless=False, wizard_mode=self.wizard_mode)
            await browser.start()
            try:
                url = self.session["url"]
                print(f"Opening {url} ...")
                print("1. Please Navigate / Search / Filter to reach your target data.")
                print("2. Log in if required.")
                print("3. Ensure the data you want to scrape is VISIBLE on screen.")
                print("   (ScrapeWizard will capture your final page state and session)")
                await browser.navigate(url)
                
                input("Press ENTER when you are ready to scrape this exact view...")
                
                cookies = await browser.get_cookies()
                storage_state = await browser.get_storage_state()
                final_url = browser.page.url
                
                with open(self.project_dir / "cookies.json", "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                
                with open(self.project_dir / "storage_state.json", "w", encoding="utf-8") as f:
                    json.dump(storage_state, f, indent=2)
                
                self.session["url"] = final_url
                self.session["login_performed"] = True
                
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
        if self.wizard_mode:
            print("\n🧠 Understanding this page…\n")
        else:
            log("Starting Reconnaissance...")
        
        cookies = None
        cookie_file = self.project_dir / "cookies.json"
        if cookie_file.exists():
            with open(cookie_file) as f:
                cookies = json.load(f)

        storage_state = None
        storage_file = self.project_dir / "storage_state.json"
        if storage_file.exists():
            with open(storage_file) as f:
                storage_state = json.load(f)

        async def do_recon():
            # Use headed mode if login was performed, as requested by user
            use_headless = not self.session.get("login_performed", False)
            browser = BrowserManager(headless=use_headless, storage_state=storage_state, wizard_mode=self.wizard_mode)
            await browser.start()
            try:
                # If no storage_state but we have legacy cookies, inject them
                if not storage_state and cookies:
                    await browser.inject_cookies(cookies)
                    
                await browser.navigate(self.session["url"])
                
                # 1. Run Behavioral Scan
                scanner = Scanner(browser.page)
                scan_profile = await scanner.scan(self.session["url"], wizard_mode=self.wizard_mode)
                
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
                        
                    # Capture full storage state after solve
                    storage_state = await browser.get_storage_state()
                    with open(self.project_dir / "storage_state.json", "w", encoding="utf-8") as f:
                        json.dump(storage_state, f, indent=2)
                        
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
        agent = UnderstandingAgent(self.project_dir, wizard_mode=self.wizard_mode)
        
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
                if self.wizard_mode:
                    pass  # Wizard mode: auto-continue
                elif not UI.override_llm_hallucination(understanding.get("reason", "Unknown")):
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
            recommended_mode = understanding.get("recommended_browser_mode", "headless")
            reason = understanding.get("reason", "No reason provided")
            
            # If login was performed, Force Headed as per user request
            if self.session.get("login_performed", False):
                recommended_mode = "headed"
                reason = "Login was performed earlier. Headed mode is REQUIRED to maintain the authenticated session and bypass anti-bot measures."

            browser_mode = UI.confirm_browser_mode(recommended_mode, reason, wizard_mode=self.wizard_mode)
        
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
        agent = CodeGenerator(self.project_dir, wizard_mode=self.wizard_mode)
        
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
        if not self.wizard_mode:
            log("Running auto-test on generated scraper...")
        
        success, output = ScriptTester.run_test(
            self.project_dir / "generated_scraper.py",
            self.project_dir,
            timeout=120,
            wizard_mode=self.wizard_mode
        )
        
        if success:
            if not self.wizard_mode:
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
                    if not self.wizard_mode:
                        log("User requested regeneration.")
                    self._transition_to(State.CODEGEN)
                else:  # abort
                    if not self.wizard_mode:
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
        loop = RepairLoop(self.project_dir, wizard_mode=self.wizard_mode)
        
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
                timeout=120,
                wizard_mode=self.wizard_mode
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
                    if not self.wizard_mode:
                        log("User requested another fix round.")
                    # Stay in REPAIR but we've exhausted attempts
                    self._transition_to(State.FAILED)
                elif action == "retry":
                    if not self.wizard_mode:
                        log("User requested regeneration.")
                    self._transition_to(State.CODEGEN)
                else:
                    if not self.wizard_mode:
                        log("User aborted.")
                    self._transition_to(State.DONE)
            else:
                if UI.approve_run():
                    self._transition_to(State.APPROVED)
                else:
                    self._transition_to(State.DONE)
        else:
            if not self.wizard_mode:
                log("Repair failed. Proceeding to DONE (failed state).")
            self._transition_to(State.FAILED)

    def _handle_final_run(self):
        """Final scraping run and bundle output."""
        if not self.wizard_mode:
            log("Starting Final Run...")
        
        # Final run gets a much longer timeout (10 minutes)
        success, output = ScriptTester.run_test(
            self.project_dir / "generated_scraper.py",
            self.project_dir,
            timeout=600,
            wizard_mode=self.wizard_mode
        )
        
        if success:
            # Bundle all project files into output folder
            self._bundle_output()
            
            if self.wizard_mode:
                output_format = self.session.get('format', 'xlsx')
                output_file = self.project_dir / "output" / f"data.{output_format}"
                print(f"\n✅ Done!\n")
                print(f"Your data is ready:")
                print(f"{output_file}\n")
            else:
                log(f"Final run complete. All files bundled in {self.project_dir}/output")
            self._transition_to(State.DONE)
        else:
            if not self.wizard_mode:
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
        
        if not self.wizard_mode:
            log("Project files bundled into output folder.")
