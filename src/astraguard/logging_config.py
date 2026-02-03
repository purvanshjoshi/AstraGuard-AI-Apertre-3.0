"""AstraGuard Structured Logging Module.

JSON-based structured logging for enterprise observability (Azure Monitor compatible).
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
from pythonjsonlogger import jsonlogger
from core.secrets import get_secret

# ============================================================================
# STRUCTURED LOGGING CONFIGURATION
# ============================================================================

def setup_json_logging(
    log_level: str = "INFO",
    service_name: str = "astra-guard",
    environment: str = get_secret("environment", "development")
):
    """Sets up JSON structured logging.

    Configures structlog and the root logger for JSON output, making it compatible with
    Azure Monitor, ELK Stack, Splunk, etc.  It also binds global context variables for
    service name, environment, and application version.

    Args:
        log_level: The logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        service_name: The name of the service.
        environment: The environment name (e.g., "development", "staging", "production").

    Returns:
        None.
    """
    
    # Configure structlog for structured output
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure root logger with JSON handler
    json_handler = logging.StreamHandler(sys.stdout)
    json_formatter = jsonlogger.JsonFormatter(
        fmt='%(timestamp)s %(level)s %(name)s %(message)s',
        timestamp=True
    )
    json_handler.setFormatter(json_formatter)
    
    # Configure Python logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.handlers.clear()
    root_logger.addHandler(json_handler)
    
    # Add global context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
        version=get_secret("app_version", "1.0.0")
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Gets a structured logger instance.

    Args:
        name: Logger name (typically `__name__`).

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)


# ============================================================================
# LOGGING CONTEXT MANAGERS
# ============================================================================

class LogContext:
    """Context manager for scoped logging context.

    Provides a context in which additional key-value pairs are added to each log message.
    """
    
    def __init__(self, logger: structlog.BoundLogger, **context):
        """Initializes the LogContext.

        Args:
            logger: The structlog logger instance.
            **context: Additional key-value pairs to add to the logging context.
        """
        self.logger = logger
        self.context = context
    
    def __enter__(self) -> structlog.BoundLogger:
        """Enters the logging context.

        Binds the logger with the specified context.

        Returns:
            The bound logger instance.
        """
        self.logger = self.logger.bind(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exits the logging context.

        Logs an error if an exception occurred within the context.

        Args:
            exc_type: The type of the exception, if any.
            exc_val: The exception instance, if any.
            exc_tb: The traceback, if any.

        Returns:
            None.
        """
        if exc_type is not None:
            self.logger.error(
                "context_error",
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    **extra
):
    """Logs an HTTP request with structured data.

    Args:
        logger: The structlog logger instance.
        method: The HTTP method (e.g., "GET", "POST").
        endpoint: The request endpoint.
        status: The HTTP status code.
        duration_ms: The request duration in milliseconds.
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "http_request",
        method=method,
        endpoint=endpoint,
        status=status,
        duration_ms=round(duration_ms, 2),
        **extra
    )


def log_error(
    logger: structlog.BoundLogger,
    error: Exception,
    context: str,
    **extra
):
    """Logs an error with full context and stack trace.

    Args:
        logger: The structlog logger instance.
        error: The exception instance.
        context: A description of the context in which the error occurred.
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.error(
        context,
        error_type=type(error).__name__,
        error_message=str(error),
        exc_info=True,
        **extra
    )


def log_detection(
    logger: structlog.BoundLogger,
    severity: str,
    detected_type: str,
    confidence: float,
    **extra
):
    """Logs an anomaly/detection event.

    Args:
        logger: The structlog logger instance.
        severity: The severity level ("critical", "warning", "info").
        detected_type: The type of anomaly detected.
        confidence: The confidence score (0.0-1.0).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "anomaly_detected",
        severity=severity,
        type=detected_type,
        confidence=round(confidence, 3),
        **extra
    )


def log_circuit_breaker_event(
    logger: structlog.BoundLogger,
    event: str,
    breaker_name: str,
    state: str,
    reason: Optional[str] = None,
    **extra
):
    """Logs a circuit breaker state change event.

    Args:
        logger: The structlog logger instance.
        event: The event type ("opened", "closed", "reset", "half_open").
        breaker_name: The name of the circuit breaker.
        state: The current state of the circuit breaker.
        reason: The reason for the state change (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.warning(
        "circuit_breaker_event",
        event=event,
        breaker=breaker_name,
        state=state,
        reason=reason,
        **extra
    )


def log_retry_event(
    logger: structlog.BoundLogger,
    endpoint: str,
    attempt: int,
    status: str,
    delay_ms: Optional[float] = None,
    **extra
):
    """Logs a retry attempt.

    Args:
        logger: The structlog logger instance.
        endpoint: The endpoint being retried.
        attempt: The attempt number.
        status: The status of the retry ("retrying", "success", "exhausted").
        delay_ms: The delay before the next retry in milliseconds (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    level = "info" if status == "retrying" else "warning"
    getattr(logger, level)(
        "retry_event",
        endpoint=endpoint,
        attempt=attempt,
        status=status,
        delay_ms=delay_ms,
        **extra
    )


def log_recovery_action(
    logger: structlog.BoundLogger,
    action_type: str,
    status: str,
    component: str,
    duration_ms: Optional[float] = None,
    **extra
):
    """Logs a recovery/remediation action.

    Args:
        logger: The structlog logger instance.
        action_type: The type of recovery action.
        status: The status of the recovery action ("started", "completed", "failed").
        component: The component being recovered.
        duration_ms: The duration of the recovery action in milliseconds (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    logger.info(
        "recovery_action",
        action=action_type,
        status=status,
        component=component,
        duration_ms=duration_ms,
        **extra
    )


def log_performance_metric(
    logger: structlog.BoundLogger,
    metric_name: str,
    value: float,
    unit: str = "ms",
    threshold: Optional[float] = None,
    **extra
):
    """Logs a performance metric.

    Args:
        logger: The structlog logger instance.
        metric_name: The name of the metric.
        value: The metric value.
        unit: The unit of measurement (default: "ms").
        threshold: An SLO threshold for comparison (optional).
        **extra: Additional context fields to include in the log.

    Returns:
        None.
    """
    alert = False
    if threshold is not None and value > threshold:
        alert = True
        log_level = "warning"
    else: 
        log_level = "info"
    
    getattr(logger, log_level)(
        "performance_metric",
        metric=metric_name,
        value=round(value, 2),
        unit=unit,
        threshold=threshold,
        alert=alert,
        **extra
    )


# ============================================================================
# FILTERING AND UTILITIES
# ============================================================================

def set_log_level(level: str):
    """Changes the logging level at runtime.

    Args:
        level: The new logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").

    Returns:
        None.
    """
    logging.getLogger().setLevel(getattr(logging, level))


def clear_context():
    """Clears all context variables.

    Returns:
        None.
    """
    structlog.contextvars.clear_contextvars()


def bind_context(**context):
    """Adds context variables to all future log entries.

    Args:
        **context: Key-value pairs to add to the logging context.

    Returns:
        None.
    """
    structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys):
    """Removes context variables.

    Args:
        *keys: Variable number of keys to remove from the context.

    Returns:
        None.
    """
    structlog.contextvars.unbind_contextvars(*keys)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize on import
if get_secret("enable_json_logging", False):
    setup_json_logging()
