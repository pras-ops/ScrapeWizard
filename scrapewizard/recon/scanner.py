import asyncio
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
from playwright.async_api import Page, Error as PlaywrightError
from scrapewizard.core.logging import log

from scrapewizard.core.constants import DEFAULT_BROWSER_TIMEOUT

class Scanner:
    """
    Performs high-level behavioral scanning of a webpage.
    Measures DOM growth, timing, mutations, network, and framework signals.
    """

    def __init__(self, page: Page):
        self.page = page
        self.scan_profile = {
            "network_activity": {
                "request_count": 0,
                "api_endpoints": [],
                "json_responses": [],
                "realtime_connections": []
            },
            "performance": {},
            "iframes": {},
            "errors": []
        }
        self.start_time = 0.0

    async def scan(self, url: str, wizard_mode: bool = False, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute the full behavioral scan pipeline.
        """
        if not wizard_mode:
            log(f"Starting behavioral scan for {url}")
        self.start_time = asyncio.get_event_loop().time()
        
        # 1. Attach Network Listeners
        self._attach_network_listeners()
        
        # 2. Initial Navigation (Baseline)
        try:
            # Use provided timeout or default (multiplied by 1000 for ms)
            timeout_ms = (timeout or DEFAULT_BROWSER_TIMEOUT) * 1000
            await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            self.scan_profile["performance"]["dom_ready_ms"] = (asyncio.get_event_loop().time() - self.start_time) * 1000
        except asyncio.TimeoutError:
            self._log_error("Initial navigation timed out", level="warning")
            return self.scan_profile
        except PlaywrightError as e:
            self._log_error(f"Playwright navigation error: {e.message}", level="error")
            return self.scan_profile
        except Exception as e:
            self._log_error(f"Unexpected navigation error: {e}", level="error")
            return self.scan_profile
            
        # 3. Pre-Render DOM Snapshot
        self.scan_profile["pre_render"] = await self._safe_call(self._get_dom_stats, "pre_render")
        
        # 4. JS Render & Hydration Observation (Network + DOM Aware)
        if not wizard_mode:
            log("Waiting for JS render and hydration...")
        try:
            # Use a slightly shorter timeout for networkidle check within the scan
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            if not wizard_mode:
                log("Network idle timeout reached, proceeding with scan.", level="warning")
            
        self.scan_profile["post_render_stability"] = await self._safe_call(self._wait_for_dom_stability, "stability")
        self.scan_profile["post_render_stats"] = await self._safe_call(self._get_dom_stats, "post_render")
        
        # 5. Mutation Rate (DOM Volatility)
        if not wizard_mode:
            log("Measuring DOM mutation rate...")
        self.scan_profile["mutation_stats"] = await self._safe_call(self._measure_mutations, "mutations")
        
        # 6. Scroll Dependency & Lazy Loading
        if not wizard_mode:
            log("Checking scroll dependency and lazy loading...")
        self.scan_profile["scroll_dependency"] = await self._safe_call(self._check_scroll_dependency, "scroll")
        
        # 7. Framework & Technical Fingerprinting
        if not wizard_mode:
            log("Fingerprinting framework and tech...")
        self.scan_profile["tech_stack"] = {
            "framework": await self._safe_call(self._detect_framework, "framework_detect"),
            "shadow_dom": await self._safe_call(self._detect_shadow_dom, "shadow_dom_detect"),
            "anti_bot": await self._safe_call(self._detect_anti_bot_signals, "anti_bot_detect"),
            "bot_defense": await self._safe_call(self._detect_bot_defense_signals, "bot_defense"),
            "signin_requirement": await self._safe_call(self._detect_signin_requirement, "signin_detect")
        }
        
        if not wizard_mode:
            log("Collecting technical metadata...")
        self.scan_profile["iframes"] = await self._safe_call(self._detect_iframes, "iframes")
        self.scan_profile["realtime_connections"] = await self._safe_call(self._detect_realtime_connections, "realtime")
        self.scan_profile["performance"]["load_time_ms"] = (asyncio.get_event_loop().time() - self.start_time) * 1000
        self.scan_profile["performance"]["total_requests"] = self.scan_profile["network_activity"]["request_count"]
        
        # 9. Structural Analysis
        if not wizard_mode:
            log("Analyzing structural signals...")
        self.scan_profile["structural_signals"] = {
            "nav_ratio": await self._safe_call(self._get_nav_ratio, "nav_ratio"),
            "accessibility": await self._safe_call(self._get_accessibility_signals, "accessibility"),
            "repeating_units": await self._safe_call(self._detect_repeating_units, "repeating_units")
        }
        
        # 10. Browser Mode Recommendation
        if not wizard_mode:
            log("Synthesizing browser mode recommendation...")
        self.scan_profile["browser_mode_recommendation"] = await self._safe_call(self._decide_browser_mode, "browser_mode")
        
        # 11. Complexity & Access Recommendation
        anti_bot = self.scan_profile["tech_stack"].get("anti_bot") or {}
        mutation_stats = self.scan_profile.get("mutation_stats") or {}
        scroll_dep = self.scan_profile.get("scroll_dependency") or {}
        
        behavioral_data = {
            "mutation_rate_per_sec": mutation_stats.get("mutation_rate_per_sec", 0),
            "scroll_dependency": scroll_dep,
            "captcha_detected": anti_bot.get("captcha", False),
            "cloudflare_detected": anti_bot.get("cloudflare", False)
        }
        
        fw = self.scan_profile["tech_stack"].get("framework", "unknown")
        tech_data = self.scan_profile["tech_stack"].copy()
        tech_data["is_spa"] = fw in ["react", "vue", "angular", "svelte"]
        
        # 1. Base Complexity
        complexity_score, access_rec, reasons = self._calculate_complexity_score(behavioral_data, tech_data)
        
        # 2. Hostility Check
        hostility_score, hostility_reasons = self._calculate_hostility_score(
            tech_data.get("bot_defense", {}), 
            self.scan_profile["network_activity"]
        )
        
        # 3. Sign-In Requirement Check
        signin_data = tech_data.get("signin_requirement") or {}
        if signin_data.get("signin_detected"):
            signin_score = signin_data.get("signin_likelihood_score", 0)
            signin_reasons = signin_data.get("signin_reasons", [])
            # Treat sign-in as hostility - forces Guided mode
            hostility_score = max(hostility_score, signin_score)
            hostility_reasons.extend(signin_reasons)
        
        # DEBUG PRINTS - hide in wizard mode
        if not wizard_mode:
            log(f"Complexity: {complexity_score}, Hostility: {hostility_score}")
        
        # 4. Override Logic
        if hostility_score >= 40:
            access_rec = "guided"
            # Prioritize hostility reasons
            reasons = list(set(["Hostile Bot Defense Detected"] + hostility_reasons + reasons))
            # Hostility dictates the final complexity score heavily
            complexity_score = max(complexity_score, hostility_score) 
        else:
            # Add minor hostility signals if any
            if hostility_score > 0:
                 complexity_score += hostility_score
                 reasons.extend(hostility_reasons)
        
        # Update profile with calculated values
        self.scan_profile["behavioral"] = behavioral_data
        self.scan_profile["complexity_score"] = complexity_score
        self.scan_profile["hostility_score"] = hostility_score
        self.scan_profile["access_recommendation"] = access_rec
        self.scan_profile["complexity_reasons"] = reasons
        
        if not wizard_mode:
            log(f"Complexity Score: {complexity_score}/100 ({'GUIDED' if access_rec == 'guided' else 'AUTOMATIC'} Mode Recommended)")
            log("Behavioral scan complete.")
        return self.scan_profile

    def _attach_network_listeners(self) -> None:
        """Set up request/response monitoring."""
        def handle_request(request):
            self.scan_profile["network_activity"]["request_count"] += 1
            url = request.url
            if any(term in url.lower() for term in ["/api/", "graphql", ".json", "query"]):
                self.scan_profile["network_activity"]["api_endpoints"].append({
                    "url": url[:200],
                    "method": request.method,
                    "resource_type": request.resource_type
                })
            
            # WebSocket Upgrade Detection
            if request.headers.get("upgrade", "").lower() == "websocket":
                self.scan_profile["network_activity"]["realtime_connections"].append({
                    "type": "websocket",
                    "url": url[:200]
                })

        def handle_response(response):
            try:
                if "application/json" in response.headers.get("content-type", "").lower():
                    # Use post_data_buffer to avoid UnicodeDecodeError on binary data
                    size = 0
                    try:
                        if response.request.post_data_buffer:
                            size = len(response.request.post_data_buffer)
                    except:
                        pass

                    self.scan_profile["network_activity"]["json_responses"].append({
                        "url": response.url[:200],
                        "status": response.status,
                        "size": size
                    })
            except Exception:
                # Silently catch listener errors to avoid crashing the scan
                pass

        self.page.on("request", handle_request)
        self.page.on("response", handle_response)

    async def _safe_call(self, func, label: str, *args) -> Any:
        """Wrap scan steps with error handling."""
        try:
            return await func(*args)
        except PlaywrightError as e:
            self._log_error(f"Playwright error in {label}: {e.message}", level="error")
            return None
        except Exception as e:
            self._log_error(f"Unexpected error in {label}: {e}", level="error")
            return None

    def _log_error(self, message: str, level: str = "warning"):
        """Centralized error logging for scanner with context."""
        log(f"Scanner [{message}]", level=level)
        if level == "error":
             log(f"Scanner Traceback: {traceback.format_exc()}", level="debug")
        self.scan_profile["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "level": level,
            "traceback": traceback.format_exc() if level == "error" else None
        })

    async def _decide_browser_mode(self) -> str:
        """
        Analyze current scan signals to recommend headless vs headed mode.
        """
        signals = {
            "captcha": self.scan_profile["tech_stack"]["anti_bot"].get("captcha", False),
            "cloudflare": self.scan_profile["tech_stack"]["anti_bot"].get("cloudflare", False),
            "low_node_count": self.scan_profile["post_render_stats"].get("node_count", 0) < 100 if self.scan_profile.get("post_render_stats") else True,
            "shadow_dom": self.scan_profile["tech_stack"].get("shadow_dom", False),
            "sse_websocket": self.scan_profile["realtime_connections"].get("has_sse", False) or \
                             self.scan_profile["realtime_connections"].get("websocket_count", 0) > 0 if self.scan_profile.get("realtime_connections") else False
        }
        
        # Consolidation logic
        if signals["captcha"] or signals["cloudflare"]:
            return "headed"
            
        if signals["low_node_count"] and self.scan_profile["network_activity"]["request_count"] > 10:
            # High network activity but low node count suggests a block or empty shell
            return "headed"
            
        # If it's a complex SPA with real-time needs, headed is safer during development
        if signals["shadow_dom"] and signals["sse_websocket"]:
            return "headed"
            
        return "headless"

    def _calculate_complexity_score(self, behavioral: Dict[str, Any], tech: Dict[str, Any]) -> Tuple[int, str, List[str]]:
        """
        Calculate complexity score (0-100) and access recommendation.
        Score > 40 implies 'Guided Mode' is safer.
        """
        score = 0
        reasons = []

        # 1. Anti-bot signals (Heavy weight)
        if behavioral.get("captcha_detected"):
            score +=50
            reasons.append("CAPTCHA detected")
        if behavioral.get("cloudflare_detected"):
            score += 40
            reasons.append("Cloudflare detected")
        
        # 2. SPA signals (Medium weight)
        if tech.get("is_spa"):
            score += 20
            reasons.append("SPA Framework detected")
        if behavioral.get("mutation_rate_per_sec", 0) > 0.5:
            score += 15
            reasons.append("High DOM mutation rate")

        # 3. Dynamic Hydration / Lazy Loading
        if behavioral.get("scroll_dependency", {}).get("content_increases_on_scroll"):
            score += 15
            reasons.append("Infinite scroll / Lazy loading")
        
        # Recommendation
        if score >= 40:
            recommendation = "guided"
        else:
            recommendation = "automatic"
            
        return score, recommendation, reasons

    async def _get_dom_stats(self) -> Dict[str, Any]:
        return await self.page.evaluate("""
        () => {
          const nodes = document.querySelectorAll('*').length;
          const depths = [...document.querySelectorAll('*')].map(el => {
            let d = 0, p = el;
            while (p) { d++; p = p.parentElement }
            return d;
          });
          return {
            node_count: nodes,
            avg_depth: depths.length ? depths.reduce((a,b)=>a+b,0)/depths.length : 0,
            max_depth: depths.length ? Math.max(...depths) : 0
          };
        }
        """)

    async def _wait_for_dom_stability(self, stable_ms: int = 800) -> Dict[str, Any]:
        last_count = 0
        stable_for = 0
        start_time = asyncio.get_event_loop().time()
        
        while stable_for < stable_ms:
            count = await self.page.evaluate("document.querySelectorAll('*').length")
            if count == last_count:
                stable_for += 100
            else:
                stable_for = 0
            last_count = count
            await asyncio.sleep(0.1)
            if asyncio.get_event_loop().time() - start_time > 5: # Max 5s wait
                break
                
        return {
            "stable_node_count": last_count,
            "stability_reached_ms": (asyncio.get_event_loop().time() - start_time) * 1000
        }

    async def _measure_mutations(self) -> Dict[str, Any]:
        await self.page.evaluate("""
        () => {
          window.__mutationCount = 0;
          const observer = new MutationObserver(mutations => {
            window.__mutationCount += mutations.length;
          });
          observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true
          });
          setTimeout(() => observer.disconnect(), 4000);
        }
        """)
        await asyncio.sleep(4.1)
        mutation_count = await self.page.evaluate("window.__mutationCount || 0")
        return {
            "mutation_count_4s": mutation_count,
            "mutation_rate_per_sec": mutation_count / 4
        }

    async def _check_scroll_dependency(self) -> Dict[str, Any]:
        before_scroll = await self.page.evaluate("document.querySelectorAll('*').length")
        
        # Detect lazy images before scroll
        lazy_images_before = await self.page.evaluate("""
            () => document.querySelectorAll('img[loading="lazy"], img[data-src]').length
        """)
        
        await self.page.mouse.wheel(0, 3000)
        await asyncio.sleep(2.5) # Enough for lazy loads to start
        
        after_scroll = await self.page.evaluate("document.querySelectorAll('*').length")
        return {
            "content_increases_on_scroll": after_scroll > before_scroll,
            "new_nodes_after_scroll": after_scroll - before_scroll,
            "lazy_images_count": lazy_images_before,
            "intersection_observer_usage": await self.page.evaluate("!!window.IntersectionObserver")
        }

    async def _detect_iframes(self) -> Dict[str, Any]:
        """Detect and count iframes, noting their sources."""
        iframes = await self.page.query_selector_all("iframe")
        sources = []
        for frame in iframes:
            try:
                src = await frame.get_attribute("src")
                if src: sources.append(src[:100])
            except:
                continue
        return {
            "count": len(iframes),
            "sources": sources[:5] # Top 5 for context
        }

    async def _detect_realtime_connections(self) -> Dict[str, Any]:
        """Detect SSE and Other real-time patterns."""
        has_sse = await self.page.evaluate("!!window.EventSource")
        # Websockets were already captured in listeners, but we can verify here
        return {
            "has_sse": has_sse,
            "websocket_count": len(self.scan_profile["network_activity"]["realtime_connections"])
        }

    async def _detect_framework(self) -> str:
        return await self.page.evaluate("""
        () => {
          if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) return "react";
          if (document.querySelector('[data-v-]')) return "vue";
          if (document.querySelector('[ng-version]')) return "angular";
          if (window.Svelte) return "svelte";
          return "unknown";
        }
        """)

    async def _detect_shadow_dom(self) -> bool:
        return await self.page.evaluate("""
        () => [...document.querySelectorAll('*')].some(el => el.shadowRoot)
        """)

    async def _detect_anti_bot_signals(self) -> Dict[str, Any]:
        return await self.page.evaluate("""
        () => ({
          captcha: !!document.querySelector('iframe[src*="captcha"], [id*="captcha"]'),
          cookie_wall: !!document.querySelector('[id*="cookie"], [class*="cookie"]'),
          cloudflare: !!document.title.includes("Cloudflare") || !!document.querySelector('#cf-wrapper')
        })
        """)
    
    async def _detect_signin_requirement(self) -> Dict[str, Any]:
        """
        Detect if the page requires or suggests sign-in/authentication.
        """
        result = await self.page.evaluate("""
        () => {
            const loginSelectors = [
                'a[href*="login"]', 'a[href*="signin"]', 'a[href*="sign-in"]',
                'a[href*="account"]', 'button[id*="login"]', 'button[id*="signin"]',
                'a[id*="nav-link-accountList"]',
                'a[data-nav-ref*="sign"]',
                '#nav-signin-tooltip', '.sign-in-tooltip'
            ];
            
            let loginElements = 0;
            loginSelectors.forEach(sel => {
                try { loginElements += document.querySelectorAll(sel).length; }
                catch (e) { }
            });
            
            const authIndicators = [
                '[data-requires-auth]',
                '.requires-login',
                '[data-login-required]'
            ];
            
            let authBlocks = 0;
            authIndicators.forEach(sel => {
                try { authBlocks += document.querySelectorAll(sel).length; }
                catch (e) { }
            });
            
            const bodyText = document.body.innerText.toLowerCase();
            const authKeywords = [
                'sign in to continue',
                'login to view',
                'please log in',
                'authentication required',
                'sign in for price',
                'sign in to see'
            ];
            
            const textMatches = authKeywords.filter(kw => bodyText.includes(kw)).length;
            const blurredContent = document.querySelectorAll('[class*="blur"], [style*="blur"]').length;
            const overlays = document.querySelectorAll('[class*="overlay"], [class*="modal"][data-auth]').length;
            
            return {
                login_buttons_count: loginElements,
                auth_blocks_count: authBlocks,
                auth_text_matches: textMatches,
                blurred_content: blurredContent,
                auth_overlays: overlays
            };
        }
        """)
        
        # Scoring logic
        signin_likelihood = 0
        reasons = []
        
        if result["login_buttons_count"] > 0:
            signin_likelihood += 20
            reasons.append(f"Login buttons detected ({result['login_buttons_count']})")
        
        if result["auth_blocks_count"] > 0:
            signin_likelihood += 30
            reasons.append("Auth-required content blocks found")
        
        if result["auth_text_matches"] > 0:
            signin_likelihood += 40
            reasons.append("Authentication prompts in text")
        
        if result["blurred_content"] > 0:
            signin_likelihood += 25
            reasons.append("Blurred/restricted content")
        
        if result["auth_overlays"] > 0:
            signin_likelihood += 35
            reasons.append("Authentication overlays")
        
        # Check URL patterns
        url = self.page.url.lower()
        if any(domain in url for domain in ["amazon", "linkedin", "facebook", "twitter", "instagram"]):
            signin_likelihood += 30
            reasons.append("Known auth-heavy platform")
        
        return {
            "signin_likelihood_score": signin_likelihood,
            "signin_detected": signin_likelihood >= 40,
            "signin_reasons": reasons,
            **result
        }

    async def _detect_bot_defense_signals(self) -> Dict[str, Any]:
        """Deep scan for specific bot defense vendors."""
        cookies = await self.page.context.cookies()
        cookie_names = [c["name"].lower() for c in cookies]
        bot_cookies = [
             "_abck", "bm_sz", "ak_bmsc", # Akamai
            "px3", "pxvid", # PerimeterX
            "cf_clearance", # Cloudflare
            "datadome", # DataDome
            "kasada", # Kasada
            "incap_ses", "visid_incap" # Imperva
        ]
        found_cookies = [c for c in bot_cookies if c in cookie_names]
        
        script_srcs = await self.page.evaluate("""
        () => Array.from(document.scripts).map(s => s.src || "").filter(s => s)
        """)
        bad_scripts = [
            "akamai", "perimeterx", "px-cdn", "datadome", "kasada", "botd", "fingerprint", "challenge"
        ]
        found_scripts = []
        for src in script_srcs:
            if any(b in src.lower() for b in bad_scripts):
                found_scripts.append(src[:50])

        honeypots = await self.page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll("input"));
            return inputs.filter(i => 
                i.style.display === "none" || 
                i.style.visibility === "hidden" || 
                i.getAttribute("aria-hidden") === "true"
            ).length
        }
        """)

        return {
            "found_cookies": found_cookies,
            "found_scripts": list(set(found_scripts)),
            "honeypots": honeypots
        }
        
    def _calculate_hostility_score(self, defense: Dict[str, Any], network: Dict[str, Any]) -> Tuple[int, List[str]]:
        score = 0
        reasons = []
        
        if defense.get("found_cookies"):
            score += 50
            reasons.append(f"Bot Cookies: {', '.join(defense['found_cookies'])}")
            
        if defense.get("found_scripts"):
            score += 30
            reasons.append("Bot Defense Scripts detected")
            
        if defense.get("honeypots", 0) > 0:
            score += 20
            reasons.append(f"Honeypots detected ({defense['honeypots']})")
            
        bad_paths = ["/challenge", "/verify", "/fp", "/setup", "/perimeterx", "/akamai", "/datadome"]
        found_challenges = []
        for req in network.get("api_endpoints", []) + network.get("json_responses", []):
             if any(p in req["url"].lower() for p in bad_paths):
                 found_challenges.append(req["url"][-20:])
        
        if found_challenges:
            score += 30
            reasons.append("Challenge/Verification requests detected")
            
        return score, reasons

    async def _get_nav_ratio(self) -> Dict[str, Any]:
        return await self.page.evaluate("""
        () => {
          const links = [...document.querySelectorAll('a')];
          const nav = links.filter(a => a.closest('nav') || a.closest('header') || a.closest('footer')).length;
          return {
            total_links: links.length,
            nav_links: nav,
            content_links: links.length - nav,
            nav_ratio: links.length ? nav / links.length : 0
          };
        }
        """)

    async def _get_accessibility_signals(self) -> Dict[str, Any]:
        return await self.page.evaluate("""
        () => ({
          aria_usage: !!document.querySelector('[aria-label], [aria-labelledby]'),
          semantic_roles: !!document.querySelector('[role="list"], [role="article"], [role="main"]')
        })
        """)

    async def _detect_repeating_units(self) -> Optional[Dict[str, Any]]:
        return await self.page.evaluate("""
        () => {
          const map = {};
          document.querySelectorAll('*').forEach(el => {
            if (el.classList.length > 0) {
                const key = el.tagName + '.' + [...el.classList].sort().join('.');
                map[key] = (map[key] || 0) + 1;
            }
          });
          const entries = Object.entries(map)
            .filter(([_,c]) => c > 5)
            .sort((a,b)=>b[1]-a[1]);
          return entries.length ? { "best_candidate": entries[0][0], "count": entries[0][1] } : null;
        }
        """)
