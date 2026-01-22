import logging
import sys
import json
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Any, Dict
from pythonjsonlogger import jsonlogger

class Logger:
    """Unified logging system/manager for ScrapeWizard."""
    
    _instance = None
    
    def __init__(self):
        self.logger = logging.getLogger("scrapewizard")
        self.logger.setLevel(logging.DEBUG)
        self.handlers = []

    @classmethod
    def get_logger(cls):
        if cls._instance is None:
            cls._instance = Logger()
        return cls._instance.logger

    @classmethod
    def setup_logging(cls, log_dir: Optional[Path] = None, verbose: bool = False):
        """Configure logging with console, file, and JSON handlers."""
        logger = cls.get_logger()
        logger.handlers.clear()

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_formatter = logging.Formatter('%(message)s') # Simplified for CLI
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Master Log (Human Readable)
            master_log_path = log_dir / "master.log"
            file_handler = RotatingFileHandler(
                master_log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            # Structured JSON Log (Machine Readable)
            json_log_path = log_dir / "events.json"
            json_handler = RotatingFileHandler(
                json_log_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
            )
            json_handler.setLevel(logging.DEBUG)
            
            # Custom formatter to include all extra fields
            json_formatter = jsonlogger.JsonFormatter(
                '%(asctime)s %(name)s %(levelname)s %(message)s'
            )
            json_handler.setFormatter(json_formatter)
            logger.addHandler(json_handler)

    @classmethod
    def add_step_log(cls, log_dir: Path, step_name: str):
        """Add a specific file handler for a step (e.g., step1_login.log)."""
        logger = cls.get_logger()
        log_file = log_dir / f"{step_name}.log"
        
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return handler

    @classmethod
    def remove_handler(cls, handler):
        """Remove a specific handler (useful for cleaning up step logs)."""
        logger = cls.get_logger()
        logger.removeHandler(handler)
        handler.close()

def log(msg: str, level: str = "info", **extra: Any):
    """Convenience function for logging with optional structured data."""
    l = Logger.get_logger()
    log_func = getattr(l, level.lower(), l.info)
    # Extra fields will be captured by the JsonFormatter
    log_func(msg, extra=extra)
