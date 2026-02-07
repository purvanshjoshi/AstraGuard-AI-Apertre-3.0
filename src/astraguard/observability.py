"""
AstraGuard Prometheus Metrics Module
Core business and reliability metrics for production monitoring
"""

from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    start_http_server, REGISTRY, CollectorRegistry
)
from contextlib import contextmanager
import time
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for metrics to avoid repeated registry lookups
_metric_cache = {}

# ============================================================================
# SAFE METRIC INITIALIZATION (handles test reruns gracefully)
# ============================================================================

def _safe_create_metric(metric_class, name, *args, **kwargs):
    """Safely create metrics, handling duplicate registration in tests"""
    # Check cache first
    if name in _metric_cache:
        return _metric_cache[name]

    try:
        metric = metric_class(*args, **kwargs)
        _metric_cache[name] = metric  # Cache the metric
        return metric
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            logger.warning(f"Metric {name} already exists, attempting to retrieve from registry")
            # Metric already exists, retrieve it from registry
            for collector in REGISTRY._collector_to_names:
                if hasattr(collector, '_name') and collector._name == name:
                    _metric_cache[name] = collector  # Cache it
                    return collector
                if hasattr(collector, '_metrics'):
                    for metric_name, metric_obj in collector._metrics.items():
                        if metric_name == name:
                            _metric_cache[name] = metric_obj  # Cache it
                            return metric_obj
            # If not found in registry, log error and create with new registry
            logger.error(f"Metric {name} not found in registry after duplicate error, creating new")
            try:
                metric = metric_class(*args, **kwargs)
                _metric_cache[name] = metric  # Cache it
                return metric
            except Exception as inner_e:
                logger.error(f"Failed to create metric {name} with new registry: {inner_e}")
                raise
        else:
            logger.error(f"ValueError creating metric {name}: {e}")
            raise

# ============================================================================
# CORE HTTP METRICS
# ============================================================================
try:
    REQUEST_COUNT = Counter(
        'astra_http_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )
except ValueError as e:
    logger.error(f"Failed to create REQUEST_COUNT metric: {e}")
    REQUEST_COUNT = None

try:
    REQUEST_LATENCY = Histogram(
        'astra_http_request_duration_seconds',
        'HTTP request latency',
        ['endpoint'],
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
    )
except ValueError:
    REQUEST_LATENCY = None

try:
    ACTIVE_CONNECTIONS = Gauge(
        'astra_active_connections',
        'Active concurrent connections'
    )
except ValueError:
    ACTIVE_CONNECTIONS = None

try:
    REQUEST_SIZE = Summary(
        'astra_http_request_size_bytes',
        'HTTP request payload size'
    )
except ValueError:
    REQUEST_SIZE = None

try:
    RESPONSE_SIZE = Summary(
        'astra_http_response_size_bytes',
        'HTTP response payload size'
    )
except ValueError:
    RESPONSE_SIZE = None

# ============================================================================
# RELIABILITY SUITE METRICS (#14-19)
# ============================================================================
try:
    CIRCUIT_BREAKER_STATE = Gauge(
        'astra_circuit_breaker_state',
        'Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)',
        ['name']
    )
except ValueError:
    CIRCUIT_BREAKER_STATE = None

try:
    CIRCUIT_BREAKER_TRANSITIONS = Counter(
        'astra_circuit_breaker_transitions_total',
        'Circuit breaker state transitions',
        ['name', 'from_state', 'to_state']
    )
except ValueError:
    CIRCUIT_BREAKER_TRANSITIONS = None

try:
    RETRY_ATTEMPTS = Counter(
        'astra_retry_attempts_total',
        'Total retry attempts',
        ['endpoint', 'outcome']
    )
except ValueError:
    RETRY_ATTEMPTS = None

try:
    RETRY_LATENCY = Histogram(
        'astra_retry_latency_seconds',
        'Latency added by retry logic',
        ['endpoint'],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
    )
except ValueError:
    RETRY_LATENCY = None

try:
    CHAOS_INJECTIONS = Counter(
        'astra_chaos_injections_total',
        'Chaos experiment injections',
        ['type', 'status']
    )
except ValueError:
    CHAOS_INJECTIONS = None

try:
    CHAOS_RECOVERY_TIME = Histogram(
        'astra_chaos_recovery_time_seconds',
        'Time to recover from chaos injection',
        ['type'],
        buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
    )
except ValueError:
    CHAOS_RECOVERY_TIME = None

try:
    RECOVERY_ACTIONS = Counter(
        'astra_recovery_actions_total',
        'Recovery actions executed',
        ['type', 'status']
    )
except ValueError:
    RECOVERY_ACTIONS = None

try:
    HEALTH_CHECK_FAILURES = Counter(
        'astra_health_check_failures_total',
        'Health check failures',
        ['service']
    )
except ValueError:
    HEALTH_CHECK_FAILURES = None

# ============================================================================
# ML/ANOMALY DETECTION METRICS
# ============================================================================
try:
    ANOMALY_DETECTIONS = Counter(
        'astra_anomalies_detected_total',
        'Total anomalies detected',
        ['severity']
    )
except ValueError:
    ANOMALY_DETECTIONS = None

try:
    DETECTION_LATENCY = Histogram(
        'astra_detection_latency_seconds',
        'Anomaly detection latency',
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5)
    )
except ValueError:
    DETECTION_LATENCY = None

try:
    DETECTION_ACCURACY = Summary(
        'astra_detection_accuracy',
        'ML model detection accuracy'
    )
except ValueError:
    DETECTION_ACCURACY = None

try:
    FALSE_POSITIVES = Counter(
        'astra_false_positives_total',
        'False positive detections',
        ['detector']
    )
except ValueError:
    FALSE_POSITIVES = None

# ============================================================================
# MEMORY ENGINE METRICS
# ============================================================================
try:
    MEMORY_ENGINE_HITS = Counter(
        'astra_memory_engine_hits_total',
        'Memory engine cache hits',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_HITS = None

try:
    MEMORY_ENGINE_MISSES = Counter(
        'astra_memory_engine_misses_total',
        'Memory engine cache misses',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_MISSES = None

try:
    MEMORY_ENGINE_SIZE = Gauge(
        'astra_memory_engine_size_bytes',
        'Memory engine storage size',
        ['store_type']
    )
except ValueError:
    MEMORY_ENGINE_SIZE = None

# ============================================================================
# ERROR METRICS
# ============================================================================
try:
    ERRORS = Counter(
        'astra_errors_total',
        'Total application errors',
        ['type', 'endpoint']
    )
except ValueError:
    ERRORS = None

try:
    ERROR_LATENCY = Histogram(
        'astra_error_resolution_time_seconds',
        'Time to resolve errors',
        ['error_type'],
        buckets=(0.1, 1.0, 5.0, 10.0, 30.0)
    )
except ValueError:
    ERROR_LATENCY = None

# ============================================================================
# CONTEXT MANAGERS FOR INSTRUMENTATION
# ============================================================================

@contextmanager
def track_request(endpoint: str, method: str = "POST"):
    """Track HTTP request metrics"""
    start = time.time()
    try:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.inc()
        yield
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="200").inc()
    except Exception as e:
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="500").inc()
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint=endpoint).inc()
        raise
    finally:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.dec()


@contextmanager
def track_anomaly_detection():
    """Track anomaly detection latency and results"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if DETECTION_LATENCY:
            DETECTION_LATENCY.observe(duration)
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="anomaly_detection").inc()
        raise


@contextmanager
def track_retry_attempt(endpoint: str):
    """Track retry latency"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if RETRY_LATENCY:
            RETRY_LATENCY.labels(endpoint=endpoint).observe(duration)
    except Exception:
        raise


@contextmanager
def track_chaos_recovery(chaos_type: str):
    """Track recovery time from chaos injection"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if CHAOS_RECOVERY_TIME:
            CHAOS_RECOVERY_TIME.labels(type=chaos_type).observe(duration)
    except Exception as e:
        logger.error(f"Chaos recovery failed for {chaos_type}: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="chaos_recovery").inc()
        raise


# ============================================================================
# ASYNC CONTEXT MANAGERS FOR INSTRUMENTATION
# ============================================================================

@contextmanager
async def async_track_request(endpoint: str, method: str = "POST"):
    """Async version of track_request for async contexts"""
    start = time.time()
    try:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.inc()
        yield
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="200").inc()
    except Exception as e:
        duration = time.time() - start
        if REQUEST_LATENCY:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
        if REQUEST_COUNT:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="500").inc()
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint=endpoint).inc()
        raise
    finally:
        if ACTIVE_CONNECTIONS:
            ACTIVE_CONNECTIONS.dec()


@contextmanager
async def async_track_anomaly_detection():
    """Async version of track_anomaly_detection"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if DETECTION_LATENCY:
            DETECTION_LATENCY.observe(duration)
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="anomaly_detection").inc()
        raise


@contextmanager
async def async_track_retry_attempt(endpoint: str):
    """Async version of track_retry_attempt"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if RETRY_LATENCY:
            RETRY_LATENCY.labels(endpoint=endpoint).observe(duration)
    except Exception:
        raise


@contextmanager
async def async_track_chaos_recovery(chaos_type: str):
    """Async version of track_chaos_recovery"""
    start = time.time()
    try:
        yield
        duration = time.time() - start
        if CHAOS_RECOVERY_TIME:
            CHAOS_RECOVERY_TIME.labels(type=chaos_type).observe(duration)
    except Exception as e:
        logger.error(f"Chaos recovery failed for {chaos_type}: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="chaos_recovery").inc()
        raise


# ============================================================================
# METRICS SERVER STARTUP
# ============================================================================

def startup_metrics_server(port: int = 9090):
    """
    Start Prometheus metrics HTTP server
    
    Args:
        port: Port to expose metrics on (default: 9090)
    """
    try:
        start_http_server(port)
        print(f"✅ Metrics server started on port {port}")
        print(f"   Access metrics: http://localhost:{port}/metrics")
    except Exception as e:
        print(f"⚠️  Failed to start metrics server: {e}")


def shutdown_metrics_server():
    """Graceful shutdown of metrics server"""
    # WSGI server stops automatically when app shuts down
    pass


def get_registry() -> CollectorRegistry:
    """Get the Prometheus metrics registry"""
    return REGISTRY


# ============================================================================
# METRICS EXPORT FUNCTION
# ============================================================================

def get_metrics_endpoint() -> bytes:
    """
    Generate Prometheus-format metrics response

    Returns:
        Bytes containing all metrics in Prometheus text format
    """
    try:
        from prometheus_client import generate_latest, REGISTRY
        return generate_latest(REGISTRY)
    except Exception as e:
        logger.error(f"Failed to generate metrics endpoint: {e}")
        if ERRORS:
            ERRORS.labels(type=type(e).__name__, endpoint="metrics_endpoint").inc()
        raise
