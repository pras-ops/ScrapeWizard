/**
 * ScrapeWizard Studio: DevTools-First Bridge Engine
 * Handles modes: BROWSE (Standard Chrome) and PICKER (Inspect Element).
 */

class StudioBridge {
    constructor() {
        this.mode = 'BROWSE'; // BROWSE | PICKER
        this.overlay = null;
        this.hoveredElement = null;
        this.lockedElement = null;
        this.init();
    }

    init() {
        console.log("🛠️ DevTools Bridge Initialized");
        this.createOverlay();
        this.bindEvents();
        this.injectStyles();
    }

    injectStyles() {
        const style = document.createElement('style');
        style.id = 'sw-studio-styles';
        style.innerHTML = `
      #sw-overlay-root {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 2147483647;
      }
      .sw-highlight-box {
        position: absolute;
        pointer-events: none;
        box-sizing: border-box;
      }
      .sw-highlight-content { background-color: rgba(120, 170, 210, 0.5); }
      .sw-highlight-padding { background-color: rgba(147, 196, 125, 0.5); }
      .sw-highlight-border { background-color: rgba(255, 229, 153, 0.5); }
      .sw-highlight-margin { background-color: rgba(246, 178, 107, 0.5); }
    `;
        document.head.appendChild(style);
    }

    createOverlay() {
        this.overlayRoot = document.createElement('div');
        this.overlayRoot.id = 'sw-overlay-root';
        document.body.appendChild(this.overlayRoot);
    }

    setMode(mode) {
        console.log("Mode switch:", mode);
        this.mode = mode;
        this.clearHighlights();

        // Toggle pointer events on body for picker mode
        if (mode === 'PICKER') {
            document.body.style.cursor = 'crosshair';
        } else {
            document.body.style.cursor = 'default';
        }
    }

    bindEvents() {
        // We use a capture listener to intercept events before the page gets them
        window.addEventListener('mousemove', (e) => {
            if (this.mode === 'PICKER') {
                this.handlePickerHover(e.target);
            }
        }, true);

        window.addEventListener('click', (e) => {
            if (this.mode === 'PICKER') {
                e.preventDefault();
                e.stopPropagation();
                this.handlePickerClick(e.target);
            }
        }, true);

        window.addEventListener('scroll', () => {
            if (this.hoveredElement) this.drawBoxModel(this.hoveredElement);
        }, { passive: true });
    }

    handlePickerHover(el) {
        if (!el || el === this.overlayRoot) return;
        if (this.hoveredElement === el) return;

        this.hoveredElement = el;
        this.drawBoxModel(el);
        this.sendToBackend('hover', el);
    }

    handlePickerClick(el) {
        this.lockedElement = el;
        this.drawBoxModel(el, true);
        this.sendToBackend('select', el);
        // Exit picker mode after selection
        this.setMode('BROWSE');
    }

    clearHighlights() {
        this.overlayRoot.innerHTML = '';
    }

    drawBoxModel(el, isLocked = false) {
        this.clearHighlights();
        if (!el) return;

        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();

        const getNum = (val) => parseFloat(val) || 0;

        const padding = {
            t: getNum(style.paddingTop),
            r: getNum(style.paddingRight),
            b: getNum(style.paddingBottom),
            l: getNum(style.paddingLeft)
        };
        const border = {
            t: getNum(style.borderTopWidth),
            r: getNum(style.borderRightWidth),
            b: getNum(style.borderBottomWidth),
            l: getNum(style.borderLeftWidth)
        };
        const margin = {
            t: getNum(style.marginTop),
            r: getNum(style.marginRight),
            b: getNum(style.marginBottom),
            l: getNum(style.marginLeft)
        };

        // 1. Content Box
        this.createHighlightSubBox(
            rect.left + border.l + padding.l,
            rect.top + border.t + padding.t,
            rect.width - border.l - border.r - padding.l - padding.r,
            rect.height - border.t - border.b - padding.t - padding.b,
            'sw-highlight-content'
        );

        // 2. Padding Box (subtracting content)
        this.createHighlightSubBox(rect.left + border.l, rect.top + border.t, rect.width - border.l - border.r, rect.height - border.t - border.b, 'sw-highlight-padding');

        // 3. Border Box
        this.createHighlightSubBox(rect.left, rect.top, rect.width, rect.height, 'sw-highlight-border');

        // 4. Margin Box
        this.createHighlightSubBox(rect.left - margin.l, rect.top - margin.t, rect.width + margin.l + margin.r, rect.height + margin.t + margin.b, 'sw-highlight-margin');

        if (isLocked) {
            // Add a persistent border for selected element
            const focus = document.createElement('div');
            Object.assign(focus.style, {
                position: 'absolute',
                top: `${rect.top}px`,
                left: `${rect.left}px`,
                width: `${rect.width}px`,
                height: `${rect.height}px`,
                border: '2px solid #10b981',
                zIndex: '1',
                pointerEvents: 'none'
            });
            this.overlayRoot.appendChild(focus);
        }
    }

    createHighlightSubBox(left, top, width, height, className) {
        const box = document.createElement('div');
        box.className = `sw-highlight-box ${className}`;
        Object.assign(box.style, {
            left: `${left}px`,
            top: `${top}px`,
            width: `${width}px`,
            height: `${height}px`
        });
        this.overlayRoot.appendChild(box);
    }

    sendToBackend(type, el) {
        const result = {
            type: type,
            tag: el.tagName.toLowerCase(),
            selector: this.generateBestSelector(el),
            text: el.innerText.substring(0, 50).trim(),
            attributes: Array.from(el.attributes).reduce((acc, a) => ({ ...acc, [a.name]: a.value }), {})
        };
        if (window.onElementSelected) {
            window.onElementSelected(JSON.stringify(result));
        }
    }

    generateBestSelector(el) {
        if (el.id) return `#${el.id}`;
        const testAttr = ['data-testid', 'data-qa', 'aria-label'].find(a => el.getAttribute(a));
        if (testAttr) return `[${testAttr}="${el.getAttribute(testAttr)}"]`;

        const path = [];
        while (el && el.nodeType === Node.ELEMENT_NODE) {
            let selector = el.nodeName.toLowerCase();
            let sib = el, nth = 1;
            while (sib = sib.previousElementSibling) {
                if (sib.nodeName.toLowerCase() == selector) nth++;
            }
            if (nth != 1) selector += `:nth-of-type(${nth})`;
            path.unshift(selector);
            el = el.parentElement;
        }
        return path.join(" > ");
    }
}

window.studioBridge = new StudioBridge();
window.setStudioMode = (mode) => window.studioBridge.setMode(mode);
