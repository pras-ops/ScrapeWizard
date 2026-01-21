import asyncio
import json
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.async_api import Page
from scrapewizard.core.logging import log

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
        self.start_time = 0

    async def scan(self, url: str) -> Dict[str, Any]:
        """
        Execute the full behavioral scan pipeline.
        """
        log(f"Starting behavioral scan for {url}")
        self.start_time = asyncio.get_event_loop().time()
        
        # 1. Attach Network Listeners
        self._attach_network_listeners()
        
        # 2. Initial Navigation (Baseline)
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
            self.scan_profile["performance"]["dom_ready_ms"] = (asyncio.get_event_loop().time() - self.start_time) * 1000
        except Exception as e:
            self._log_error("navigation", e)
            return self.scan_profile
            
        # 3. Pre-Render DOM Snapshot
        self.scan_profile["pre_render"] = await self._safe_call(self._get_dom_stats, "pre_render")
        
        # 4. JS Render & Hydration Observation (Network + DOM Aware)
        log("Waiting for JS render and hydration...")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            log("Network idle timeout reached, proceeding with scan.", level="warning")
            
        self.scan_profile["post_render_stability"] = await self._safe_call(self._wait_for_dom_stability, "stability")
        self.scan_profile["post_render_stats"] = await self._safe_call(self._get_dom_stats, "post_render")
        
        # 5. Mutation Rate (DOM Volatility)
        log("Measuring DOM mutation rate...")
        self.scan_profile["mutation_stats"] = await self._safe_call(self._measure_mutations, "mutations")
        
        # 6. Scroll Dependency & Lazy Loading
        log("Checking scroll dependency and lazy loading...")
        self.scan_profile["scroll_dependency"] = await self._safe_call(self._check_scroll_dependency, "scroll")
        
        # 7. Framework & Technical Fingerprinting
        log("Fingerprinting framework and tech...")
        self.scan_profile["tech_stack"] = {
            "framework": await self._safe_call(self._detect_framework, "framework_detect"),
            "shadow_dom": await self._safe_call(self._detect_shadow_dom, "shadow_dom_detect"),
            "anti_bot": await self._safe_call(self._detect_anti_bot_signals, "anti_bot_detect")
        }
        
        log("Collecting technical metadata...")
        self.scan_profile["iframes"] = await self._safe_call(self._detect_iframes, "iframes")
        self.scan_profile["realtime_connections"] = await self._safe_call(self._detect_realtime_connections, "realtime")
        self.scan_profile["performance"]["load_time_ms"] = (asyncio.get_event_loop().time() - self.start_time) * 1000
        self.scan_profile["performance"]["total_requests"] = self.scan_profile["network_activity"]["request_count"]
        
        # 9. Structural Analysis
        log("Analyzing structural signals...")
        self.scan_profile["structural_signals"] = {
            "nav_ratio": await self._safe_call(self._get_nav_ratio, "nav_ratio"),
            "accessibility": await self._safe_call(self._get_accessibility_signals, "accessibility"),
            "repeating_units": await self._safe_call(self._detect_repeating_units, "repeating_units")
        }
        
        # 10. Browser Mode Recommendation
        log("Synthesizing browser mode recommendation...")
        self.scan_profile["browser_mode_recommendation"] = await self._safe_call(self._decide_browser_mode, "browser_mode")
        
        log("Behavioral scan complete.")
        return self.scan_profile

    def _attach_network_listeners(self):
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
            except Exception as e:
                # Silently catch listener errors to avoid crashing the scan
                pass

        self.page.on("request", handle_request)
        self.page.on("response", handle_response)

    async def _safe_call(self, func, label: str, *args):
        """Wrap scan steps with error handling."""
        try:
            return await func(*args)
        except Exception as e:
            self._log_error(label, e)
            return None

    def _log_error(self, step: str, error: Exception):
        tb = traceback.format_exc()
        log(f"Scan error in {step}: {error}\n{tb}", level="error")
        self.scan_profile["errors"].append({
            "step": step,
            "error": str(error),
            "traceback": tb
        })

    async def _decide_browser_mode(self) -> str:
        """
        Analyze current scan signals to recommend headless vs headed mode.
        """
        signals = {
            "captcha": self.scan_profile["tech_stack"]["anti_bot"].get("captcha", False),
            "cloudflare": self.scan_profile["tech_stack"]["anti_bot"].get("cloudflare", False),
            "low_node_count": self.scan_profile["post_render_stats"].get("node_count", 0) < 100,
            "shadow_dom": self.scan_profile["tech_stack"].get("shadow_dom", False),
            "sse_websocket": self.scan_profile["realtime_connections"].get("has_sse", False) or \
                             self.scan_profile["realtime_connections"].get("websocket_count", 0) > 0
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
