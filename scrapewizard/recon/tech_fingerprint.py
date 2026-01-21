from bs4 import BeautifulSoup
from typing import List

class TechFingerprinter:
    """Detects underlying technologies and anti-bot systems."""
    
    def __init__(self, soup: BeautifulSoup):
        self.soup = soup

    def detect(self) -> List[str]:
        techs = []
        html_str = str(self.soup)
        
        if "react" in html_str or "__REACT" in html_str:
            techs.append("React")
        if "__NEXT_DATA__" in html_str:
            techs.append("Next.js")
        if "vue" in html_str or "__vue__" in html_str:
            techs.append("Vue.js")
        if "wp-content" in html_str:
            techs.append("WordPress")
        if "shopify" in html_str:
            techs.append("Shopify")
            
        # Security/Anti-bot
        if "cloudflare" in html_str:
            techs.append("Cloudflare")
            
        return techs
