"""
AstraGuard OpenTelemetry Tracing Module
Distributed tracing with Jaeger for production observability
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from contextlib import contextmanager, asynccontextmanager
import logging
import os
from typing import Optional, Any
from core.secrets import get_secret
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# ============================================================================
# JAEGER EXPORTER CONFIGURATION
# ============================================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, OSError)),
    reraise=True
)
def initialize_tracing(
    service_name: str = "astra-guard",
    jaeger_host: str = "localhost",
    jaeger_port: int = 6831,
    enabled: bool = True,
    batch_size: int = 512,
    export_interval: float = 5.0
) -> TracerProvider:
    """
    Initialize OpenTelemetry tracing with a Jaeger backend.

    Configures a global TracerProvider that exports spans to a Jaeger agent
    via gRPC. Includes automatic resource tagging (environment, version) and
    batch processing for performance.

    Robustness:
    - Retries connection failures with exponential backoff.
    - Returns a no-op provider if tracing is disabled or initialization fails.

    Args:
        service_name (str): Identifier for the service in Jaeger UI.
        jaeger_host (str): Hostname of the Jaeger agent/collector.
        jaeger_port (int): Port of the Jaeger agent/collector (default: 6831).
        enabled (bool): Global switch to enable/disable tracing.
        batch_size (int): Max number of spans to send in one batch.
        export_interval (float): Time in seconds between batch exports.

    Returns:
        TracerProvider: The configured global tracer provider.
    """
    if not enabled:
        logger.info("⚠️  Tracing disabled - using no-op tracer provider")
        return TracerProvider()
    
    try:
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
            transport_format="grpc",
        )
        
        # Create tracer provider with service resource
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "environment": get_secret("environment", "development"),
            "version": get_secret("app_version", "1.0.0"),
        })
        
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            jaeger_exporter,
            max_export_batch_size=batch_size,
            schedule_delay_millis=int(export_interval * 1000)
        )
        provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        logger.info(f"✅ Tracing initialized - Jaeger at {jaeger_host}:{jaeger_port}")
        return provider
        
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Jaeger: {e}")
        return TracerProvider()


def setup_auto_instrumentation():
    """
    Setup automatic instrumentation for common libraries
    Must be called before creating FastAPI app
    """
    try:
        # Instrument external libraries
        RequestsInstrumentor().instrument()
        RedisInstrumentor().instrument()
        logger.info("✅ Auto-instrumentation enabled for requests and Redis")
    except ImportError as e:
        logger.warning(f"⚠️  Missing instrumentation library: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to setup auto-instrumentation: {e}")


def instrument_fastapi(app):
    """
    Instrument FastAPI application with OpenTelemetry

    Args:
        app: FastAPI application instance
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("✅ FastAPI instrumented with OpenTelemetry")
    except ImportError as e:
        logger.warning(f"⚠️  Missing FastAPI instrumentation: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to instrument FastAPI: {e}")


# ============================================================================
# TRACER CONTEXT MANAGERS
# ============================================================================

def get_tracer(name: str = __name__) -> trace.Tracer:
    """Get a tracer instance"""
    return trace.get_tracer(name)


@contextmanager
def span(name: str, attributes: Optional[dict] = None):
    """
    Context manager for creating manual OpenTelemetry spans.

    Wraps a block of code in a custom span, allowing for granular performance
    tracking and attribute tagging. Automatically handles span lifecycle (start/end)
    and exception recording.

    Args:
        name (str): The operation name to display in the trace.
        attributes (Optional[dict]): Key-value pairs to annotate the span
                                     (e.g., {"user_id": "123", "retry": "true"}).

    Yields:
        trace.Span: The active span object for further customization.

    Example:
        with span("process_image", {"image_size": "1024x768"}):
            process(image)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span_obj:
        if attributes:
            for key, value in attributes.items():
                span_obj.set_attribute(key, str(value))
        yield span_obj


@contextmanager
def span_anomaly_detection(data_size: int, model_name: str = "default"):
    """
    Trace anomaly detection workflow with sub-spans
    
    Args:
        data_size: Size of input data
        model_name: Name of ML model
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("anomaly_detection") as main_span:
        main_span.set_attribute("data.size", data_size)
        main_span.set_attribute("model", model_name)
        
        try:
            yield main_span
        except Exception as e:
            main_span.record_exception(e)
            raise


@contextmanager
def span_model_inference(model_type: str, input_shape: tuple):
    """
    Trace ML model inference
    
    Args:
        model_type: Type of model (anomaly_detector, classifier, etc.)
        input_shape: Shape of input data
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("model_inference") as span_obj:
        span_obj.set_attribute("model.type", model_type)
        span_obj.set_attribute("input.shape", str(input_shape))
        yield span_obj


@contextmanager
def span_circuit_breaker(name: str, operation: str):
    """
    Trace circuit breaker operations
    
    Args:
        name: Circuit breaker name
        operation: Operation type (call, trip, reset, etc.)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("circuit_breaker") as span_obj:
        span_obj.set_attribute("breaker.name", name)
        span_obj.set_attribute("operation", operation)
        yield span_obj


@contextmanager
def span_retry(endpoint: str, attempt: int):
    """
    Trace retry attempts
    
    Args:
        endpoint: Endpoint being retried
        attempt: Attempt number
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("retry_attempt") as span_obj:
        span_obj.set_attribute("endpoint", endpoint)
        span_obj.set_attribute("attempt", attempt)
        yield span_obj


@contextmanager
def span_external_call(service: str, operation: str, timeout: float = None):
    """
    Trace external service calls (API, database, etc.)
    
    Args:
        service: External service name
        operation: Operation being performed
        timeout: Operation timeout in seconds
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("external_call") as span_obj:
        span_obj.set_attribute("service", service)
        span_obj.set_attribute("operation", operation)
        if timeout:
            span_obj.set_attribute("timeout", timeout)
        yield span_obj


@contextmanager
def span_database_query(query_type: str, table: str = None):
    """
    Trace database operations
    
    Args:
        query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
        table: Table name (if applicable)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("database_query") as span_obj:
        span_obj.set_attribute("query.type", query_type)
        if table:
            span_obj.set_attribute("table", table)
        yield span_obj


@contextmanager
def span_cache_operation(operation: str, key: str, cache_type: str = "redis"):
    """
    Trace cache operations
    
    Args:
        operation: Operation type (get, set, delete)
        key: Cache key
        cache_type: Type of cache system
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("cache_operation") as span_obj:
        span_obj.set_attribute("operation", operation)
        span_obj.set_attribute("key", key)
        span_obj.set_attribute("cache.type", cache_type)
        yield span_obj


# ============================================================================
# TRACING SHUTDOWN
# ============================================================================

def shutdown_tracing():
    """
    Gracefully shutdown tracer and flush pending spans
    Call this on application shutdown
    """
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, 'force_flush'):
            provider.force_flush()
        logger.info("✅ Tracing flushed and shutdown complete")
    except ConnectionError as e:
        logger.warning(f"⚠️  Connection error during tracing shutdown: {e}")
    except Exception as e:
        logger.warning(f"⚠️  Error during tracing shutdown: {e}")


# ============================================================================
# ASYNC CONTEXT MANAGERS
# ============================================================================

@asynccontextmanager
async def async_span(name: str, attributes: Optional[dict] = None):
    """
    Async context manager for creating spans

    Args:
        name: Span name
        attributes: Optional span attributes

    Example:
        async with async_span("database_query", {"table": "users"}):
            # Do async work
            pass
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span_obj:
        if attributes:
            for key, value in attributes.items():
                span_obj.set_attribute(key, str(value))
        yield span_obj


@asynccontextmanager
async def async_span_anomaly_detection(data_size: int, model_name: str = "default"):
    """
    Async trace anomaly detection workflow with sub-spans

    Args:
        data_size: Size of input data
        model_name: Name of ML model
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("anomaly_detection") as main_span:
        main_span.set_attribute("data.size", data_size)
        main_span.set_attribute("model", model_name)

        try:
            yield main_span
        except Exception as e:
            main_span.record_exception(e)
            raise


@asynccontextmanager
async def async_span_external_call(service: str, operation: str, timeout: float = None):
    """
    Async trace external service calls (API, database, etc.)

    Args:
        service: External service name
        operation: Operation being performed
        timeout: Operation timeout in seconds
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("external_call") as span_obj:
        span_obj.set_attribute("service", service)
        span_obj.set_attribute("operation", operation)
        if timeout:
            span_obj.set_attribute("timeout", timeout)
        yield span_obj
