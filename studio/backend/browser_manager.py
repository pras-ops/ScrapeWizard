import asyncio
from playwright.async_api import async_playwright
import os

class StudioBrowserManager:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def start(self, url: str):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        if not self.browser:
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(viewport={'width': 1280, 'height': 720})
            
            # Inject the bridge script
            bridge_path = os.path.join(os.path.dirname(__file__), '../bridge/engine.js')
            with open(bridge_path, 'r') as f:
                bridge_script = f.read()
            
            await self.context.add_init_script(bridge_script)
            await self.context.expose_function("onElementSelected", self._on_element_selected)

        if not self.page:
            self.page = await self.context.new_page()
            
            # Setup Screencast
            cdp_session = await self.page.context.new_cdp_session(self.page)
            await cdp_session.send('Page.startScreencast', {
                'format': 'jpeg',
                'quality': 60,
                'maxWidth': 1280,
                'maxHeight': 720
            })

            async def on_screencast_frame(event):
                if hasattr(self, 'on_frame'):
                    await self.on_frame(event['data'])
                await cdp_session.send('Page.screencastFrameAck', {
                    'sessionId': event['sessionId']
                })

            cdp_session.on('Page.screencastFrame', on_screencast_frame)

        await self.page.goto(url)
        return self.page

    async def get_cdp_session(self):
        if not self.page:
            raise Exception("Page not started")
        return await self.page.context.new_cdp_session(self.page)

    async def _on_element_selected(self, selector: str):
        print(f"WEB_SELECTION: {selector}")
        # This will be routed to the WebSocket in main.py
        if hasattr(self, 'on_selection'):
            await self.on_selection(selector)

    async def get_dom_tree(self):
        if not self.page:
            return None
        
        # We'll use a script to get a simplified tree for the IDE
        # Deep recursion in CDP can be heavy, so we start with a robust JS traversal
        tree = await self.page.evaluate("""() => {
            const serialize = (el) => {
                const node = {
                    tag: el.tagName.toLowerCase(),
                    attributes: Array.from(el.attributes).reduce((acc, a) => ({ ...acc, [a.name]: a.value }), {}),
                    children: []
                };
                if (el.id) node.id = el.id;
                if (el.className) node.className = el.className;
                
                // Truncate list if too long to prevent massive payloads
                const childrenToProcess = Array.from(el.children).slice(0, 500);
                
                for (const child of childrenToProcess) {
                    node.children.push(serialize(child));
                }
                
                if (el.children.length > 500) {
                     node.children.push({ tag: 'div', attributes: { class: 'sw-truncated-msg' }, children: [], text: `... ${el.children.length - 500} more items ...` });
                }
                
                // Content for leaf nodes
                if (node.children.length === 0) {
                    const text = el.innerText || el.textContent;
                    if (text && text.trim().length > 0) {
                        node.text = text.trim().substring(0, 50); // Truncate text preview
                    }
                }
                
                return node;
            };
            return serialize(document.body);
        }""")
        return tree

    async def handle_input_event(self, event_type: str, params: dict):
        if not self.page:
            return

        try:
            if event_type == 'mouse':
                x, y = params.get('x', 0), params.get('y', 0)
                action = params.get('action')
                
                if action == 'move':
                    await self.page.mouse.move(x, y)
                elif action == 'down':
                    await self.page.mouse.down()
                elif action == 'up':
                    await self.page.mouse.up()
                elif action == 'click':
                    await self.page.mouse.click(x, y)
                elif action == 'wheel':
                    await self.page.mouse.wheel(params.get('deltaX', 0), params.get('deltaY', 0))
            
            elif event_type == 'keyboard':
                action = params.get('action')
                key = params.get('key')
                if action == 'down':
                    await self.page.keyboard.down(key)
                elif action == 'up':
                    await self.page.keyboard.up(key)
                elif action == 'press':
                    await self.page.keyboard.press(key)

        except Exception as e:
            print(f"Input error: {e}")

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.playwright = None
