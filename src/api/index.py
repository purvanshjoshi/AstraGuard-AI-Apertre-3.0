"""
AstraGuard AI - Vercel Serverless Function Entry Point.

This module adapts the standard FastAPI application (`api.service.app`) regarding
Vercel's serverless environment. It handles path resolution for imports when
running in a restricted lambda environment where the project root might not be
in `sys.path` by default.
"""

import sys
import logging
from pathlib import Path
from typing import List

logger: logging.Logger = logging.getLogger(__name__)

# Resolve project root safely
try:
    project_root: Path = Path(__file__).parent.parent
except NameError as e:
    logger.critical(
        "__file__ is not defined; cannot resolve project root in serverless environment",
        exc_info=True,
    )
    raise RuntimeError("Invalid runtime environment: __file__ is undefined") from e

project_root_str: str = str(project_root)
        extra={"project_root": project_root_str},
    )

# Import FastAPI application
try:
    from api.service import app
except ModuleNotFoundError as e:
    logger.critical(
        "Failed to import 'api.service.app' (module not found). "
        "Check project structure and PYTHONPATH.",
        exc_info=True,
    )
    raise
except ImportError as e:
    logger.critical(
        "ImportError while importing 'api.service.app'. "
        "This may be caused by import-time side effects or missing dependencies.",
        exc_info=True,
    )
    raise

# This exports the FastAPI app 
__all__: List[str] = ["app"]
