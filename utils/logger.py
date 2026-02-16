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
    
    # File handler — try project dir, fallback to /tmp
    log_file = None
    for log_dir in [
        Path(__file__).parent.parent / "logs",
        Path("/tmp/lens_ai_logs"),
    ]:
        try:
            log_dir.mkdir(exist_ok=True)
            log_file = log_dir / "pipeline.log"
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_handler.setFormatter(fmt)
            logger.addHandler(file_handler)
            break
        except (PermissionError, OSError):
            continue
    
    if log_file is None:
        logger.warning("Could not create log file, running console-only")
    
    return logger


# Default logger instance
log = setup_logger()
