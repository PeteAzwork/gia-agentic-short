"""
OpenTelemetry Tracing Setup
===========================
Configures distributed tracing for the research agent workflow.

Sends traces to AI Toolkit's OTLP endpoint for visualization.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import atexit
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from src.config import TRACING

# Use centralized config
SERVICE_NAME_VALUE = TRACING.SERVICE_NAME
OTLP_ENDPOINT = TRACING.OTLP_ENDPOINT
ENABLE_TRACING = TRACING.ENABLED

# Track provider for cleanup
_provider: Optional[TracerProvider] = None


def _cleanup_tracing() -> None:
    """Shutdown the tracer provider to flush pending spans."""
    global _provider
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception:
            pass  # Best effort cleanup


def setup_tracing(service_name: str = SERVICE_NAME_VALUE) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing with OTLP export.
    
    Args:
        service_name: Name of the service for trace identification
        
    Returns:
        Configured tracer instance
    """
    global _provider
    
    # Create resource with service name
    resource = Resource.create({
        SERVICE_NAME: service_name,
    })
    
    # Set up tracer provider
    _provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter (HTTP)
    otlp_exporter = OTLPSpanExporter(
        endpoint=OTLP_ENDPOINT,
    )
    
    # Add batch processor for efficient export
    _provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # Set as global tracer provider
    trace.set_tracer_provider(_provider)
    
    # Instrument HTTP clients (for Anthropic API calls)
    HTTPXClientInstrumentor().instrument()
    
    # Register cleanup on exit to flush pending spans
    atexit.register(_cleanup_tracing)
    
    return trace.get_tracer(service_name)


def get_tracer(name: str = SERVICE_NAME_VALUE) -> trace.Tracer:
    """
    Get a tracer instance for creating spans.
    
    Args:
        name: Tracer name (usually module or component name)
        
    Returns:
        Tracer instance
    """
    return trace.get_tracer(name)


# Initialize tracing on module import
_tracer = None


def init_tracing() -> trace.Tracer:
    """
    Initialize tracing if not already done.
    
    Returns:
        The global tracer instance (or NoOp tracer if disabled)
    """
    global _tracer
    if _tracer is None:
        if ENABLE_TRACING:
            _tracer = setup_tracing()
        else:
            # Return NoOp tracer when tracing is disabled
            _tracer = trace.get_tracer(SERVICE_NAME_VALUE)
    return _tracer
