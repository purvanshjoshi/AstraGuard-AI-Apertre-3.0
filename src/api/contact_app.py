"""
Lightweight FastAPI app exposing only the contact router.
This avoids importing the full `api.service` and its heavy dependencies
so the contact endpoints can be run independently during development.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging


logger = logging.getLogger(__name__)

# Import contact router

try:
    from api.contact import router as contact_router
except ModuleNotFoundError:
    logger.critical(
        "Failed to import 'api.contact.router' (module not found). "
        "Verify project structure and PYTHONPATH.",
        exc_info=True,
    )
    raise
except ImportError:
    logger.critical(
        "ImportError occurred while importing contact router. "
        "This may be caused by missing dependencies or import-time side effects.",
        exc_info=True,
    )
    raise

# FastAPI application setup
app = FastAPI(title="AstraGuard Contact API (dev)")

# Allow local frontend (python http.server) and localhost same-origin
ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

try:
    app.include_router(contact_router)
except RuntimeError:
    logger.critical(
        "Failed to include contact router in FastAPI application.",
        exc_info=True,
    )
    raise
