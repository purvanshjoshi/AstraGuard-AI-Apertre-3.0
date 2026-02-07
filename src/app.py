"""
AstraGuard AI - Main FastAPI Application
Entry point for production deployments
"""


import logging

logger = logging.getLogger(__name__)

# Import FastAPI application

try:
    from api.service import app
except ModuleNotFoundError as e:
    logger.critical(
        "Failed to import 'api.service.app' (module not found). "
        "Verify project structure and PYTHONPATH.",
        exc_info=True,
    )
    raise
except ImportError as e:
    logger.critical(
        "ImportError occurred while importing FastAPI app. "
        "This may be caused by missing dependencies or import-time side effects.",
        exc_info=True,
    )
    raise

# Local development entry point

if __name__ == "__main__":
    try:
        import uvicorn
    except ModuleNotFoundError as e:
        logger.critical(
            "Uvicorn is required to run the application locally but is not installed.",
            exc_info=True,
        )
        raise

    try:
        uvicorn.run(app, host="0.0.0.0", port=8002)
    except RuntimeError as e:
        logger.critical(
            "Failed to start Uvicorn server.",
            exc_info=True,
        )
        raise