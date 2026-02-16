"""
Logging setup for the AI News Video Factory.
"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "newsfactory", level: int = logging.INFO) -> logging.Logger:
    """Create and configure a logger with console and file handlers."""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Format
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)
    
    # File handler
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "pipeline.log")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    
    return logger


# Default logger instance
log = setup_logger()
