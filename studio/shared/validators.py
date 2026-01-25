from pydantic import BaseModel, HttpUrl, Field, validator
from typing import Literal, Optional

class ScrapeRequest(BaseModel):
    """Validation model for a scraping request from Studio."""
    url: HttpUrl
    max_pages: int = Field(default=1, ge=1, le=1000)
    output_format: Literal['json', 'csv', 'xlsx'] = 'json'
    browser_mode: Literal['headless', 'headed'] = 'headless'
    
    @validator('url')
    def block_localhost(cls, v):
        url_str = str(v)
        if 'localhost' in url_str or '127.0.0.1' in url_str:
            raise ValueError('Localhost URLs are forbidden for security reasons.')
        return v

class SessionConfig(BaseModel):
    """Configuration for a Studio session."""
    session_id: str
    target_url: HttpUrl
    viewport: dict = {"width": 1280, "height": 720}
    user_agent: Optional[str] = None
