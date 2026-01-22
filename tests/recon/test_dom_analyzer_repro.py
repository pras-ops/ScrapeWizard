import sys
from pathlib import Path
# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from scrapewizard.recon.dom_analyzer import DOMAnalyzer
import json

mock_html = """
<html>
<body>
    <div id="search">
        <div class="s-result-item s-asin ad-id-123" data-asin="B01">
            <div class="s-card-container">
                <h2 class="a-size-mini"><span class="a-text-normal">Phone Case A</span></h2>
                <div class="a-row"><span class="a-price"><span class="a-offscreen">$10.00</span></span></div>
                <img class="s-image" src="img1.jpg">
                <a class="a-link-normal" href="/item1">View</a>
            </div>
        </div>
        <div class="s-result-item s-asin ad-id-456" data-asin="B02">
            <div class="s-card-container">
                <h2 class="a-size-mini"><span class="a-text-normal">Phone Case B</span></h2>
                <div class="a-row"><span class="a-price"><span class="a-offscreen">$12.00</span></span></div>
                <img class="s-image" src="img2.jpg">
                <a class="a-link-normal" href="/item2">View</a>
            </div>
        </div>
        <div class="s-result-item s-asin ad-id-789" data-asin="B03">
            <div class="s-card-container">
                <h2 class="a-size-mini"><span class="a-text-normal">Phone Case C</span></h2>
                <div class="a-row"><span class="a-price"><span class="a-offscreen">$15.00</span></span></div>
                <img class="s-image" src="img3.jpg">
                <a class="a-link-normal" href="/item3">View</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

def test_detection():
    analyzer = DOMAnalyzer(mock_html)
    analysis = analyzer.analyze()
    print(json.dumps(analysis, indent=2))
    
    sections = analysis.get("sections", [])
    if sections:
        print(f"\nSUCCESS: Found {len(sections)} sections")
        best = sections[0]
        print(f"Best Selector: {best['selector']}")
        print(f"Fields found: {[f['name'] for f in best['fields']]}")
    else:
        print("\nFAILURE: No sections found")

if __name__ == "__main__":
    test_detection()
