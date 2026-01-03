"""
AstraGuard AI Backend - Main FastAPI Application

Central entry point for the AstraGuard AI reliability suite backend.
Integrates:
- Issue #14: Circuit Breaker pattern
- Issue #15: Retry logic with exponential backoff
- Issue #16: Health Monitor + Fallback Cascade

API Endpoints:
- /health/metrics - Prometheus metrics
- /health/state - Comprehensive health snapshot
- /health/cascade - Trigger fallback cascade
- /health/ready - Kubernetes readiness check
- /health/live - Kubernetes liveness check
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
import uvicorn

# Import modules
from backend.health_monitor import (
    router as health_router,
    HealthMonitor,
    set_health_monitor,
)
from backend.fallback_manager import FallbackManager
from backend.recovery_orchestrator import RecoveryOrchestrator
from core.component_health import SystemHealthMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Initialize health monitor and fallback manager
health_monitor: HealthMonitor = None
fallback_manager: FallbackManager = None
recovery_orchestrator: RecoveryOrchestrator = None
component_health: SystemHealthMonitor = None


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    
    Startup: Initialize monitoring systems
    Shutdown: Cleanup resources
    """
    # ========== STARTUP ==========
    logger.info("🚀 AstraGuard AI Backend starting...")
    
    global health_monitor, fallback_manager, component_health
    
    try:
        # Initialize component health monitor
        component_health = SystemHealthMonitor()
        
        # Initialize health monitor (Issue #16)
        health_monitor = HealthMonitor(
            circuit_breaker=None,  # Will integrate with CB from Issue #14
            retry_tracker=None,    # Will integrate with Retry from Issue #15
            failure_window_seconds=3600,
        )
        
        # Initialize fallback manager (Issue #16)
        fallback_manager = FallbackManager(
            circuit_breaker=None,
            anomaly_detector=None,
            heuristic_detector=None,
        )
        
        # Initialize recovery orchestrator (Issue #17)
        recovery_orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
            config_path="config/recovery.yaml",
        )
        
        # Register health monitor with FastAPI
        set_health_monitor(health_monitor)
        
        # Register core components
        component_health.register_component(
            "anomaly_detector",
            metadata={"version": "1.0", "type": "ml"},
        )
        component_health.register_component(
            "memory_store",
            metadata={"version": "1.0", "type": "cache"},
        )
        component_health.register_component(
            "policy_engine",
            metadata={"version": "1.0", "type": "rule_engine"},
        )
        
        logger.info("✅ Health Monitor initialized")
        logger.info("✅ Fallback Manager initialized")
        logger.info("✅ Component Health Monitor initialized")
        
        # Start background health polling task
        health_task = asyncio.create_task(background_health_polling())
        logger.info("✅ Background health polling started")
        
        # Start recovery orchestrator background task (Issue #17)
        recovery_task = asyncio.create_task(recovery_orchestrator.run())
        logger.info("✅ Recovery Orchestrator started")
        
        yield  # Application runs here
        
        # ========== SHUTDOWN ==========
        logger.info("🛑 AstraGuard AI Backend shutting down...")
        
        health_task.cancel()
        recovery_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass
        
        logger.info("✅ Background tasks cancelled")
        logger.info("✅ Cleanup complete")
    
    except Exception as e:
        logger.error(f"❌ Startup error: {e}", exc_info=True)
        raise


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


async def background_health_polling():
    """
    Background task for periodic health evaluation and cascade triggering.
    
    Runs every 10 seconds:
    1. Evaluates current system health
    2. Triggers fallback cascade if needed
    3. Updates metrics
    """
    poll_interval = 10  # seconds
    
    logger.info(f"Background health polling started (interval: {poll_interval}s)")
    
    while True:
        try:
            await asyncio.sleep(poll_interval)
            
            if not health_monitor or not fallback_manager:
                continue
            
            # Get current health state
            state = await health_monitor.get_comprehensive_state()
            
            # Evaluate cascade
            new_mode = await fallback_manager.cascade(state)
            
            # Log if mode changed
            logger.debug(f"Fallback mode: {new_mode.value}")
        
        except asyncio.CancelledError:
            logger.info("Background health polling stopped")
            break
        except Exception as e:
            logger.error(f"Error in background health polling: {e}", exc_info=True)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    app = FastAPI(
        title="AstraGuard AI Backend",
        description="Reliability suite backend with observability",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ========== ROUTES ==========
    
    # Health monitor routes (Issue #16)
    app.include_router(health_router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "AstraGuard AI Backend",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health/state",
            "metrics": "/health/metrics",
            "recovery": "/recovery/status",
        }
    
    # Status endpoint
    @app.get("/status")
    async def status():
        """Get backend status."""
        if not health_monitor:
            return {"status": "initializing"}
        
        state = await health_monitor.get_comprehensive_state()
        return {
            "status": "running",
            "system_health": state.get("system", {}).get("status"),
            "fallback_mode": fallback_manager.get_mode_string() if fallback_manager else "unknown",
            "uptime_seconds": state.get("uptime_seconds", 0),
        }
    
    # Recovery Orchestrator endpoints (Issue #17)
    @app.get("/recovery/status")
    async def recovery_status():
        """Get recovery orchestrator status and metrics."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}
        
        return {
            "status": "running" if recovery_orchestrator._running else "stopped",
            "metrics": recovery_orchestrator.get_metrics(),
            "cooldowns": recovery_orchestrator.get_cooldown_status(),
            "last_actions": recovery_orchestrator.get_action_history(limit=10),
        }
    
    @app.get("/recovery/history")
    async def recovery_history(limit: int = 50):
        """Get recovery action history."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}
        
        return {"actions": recovery_orchestrator.get_action_history(limit=limit)}
    
    @app.get("/recovery/cooldowns")
    async def recovery_cooldowns():
        """Get current cooldown status for recovery actions."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}
        
        return recovery_orchestrator.get_cooldown_status()
    
    # ========== ERROR HANDLERS ==========
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return {
            "error": "Internal server error",
            "detail": str(exc),
        }
    
    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

app = create_app()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting AstraGuard AI Backend...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
