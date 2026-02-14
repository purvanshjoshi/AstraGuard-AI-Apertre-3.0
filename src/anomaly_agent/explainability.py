"""
Explainability Module for Anomaly Decisions

This module provides utilities to construct human-readable explanations for
automated anomaly detection and response decisions. It bridges the gap between
raw probability scores and operator-understandable reasoning.
"""

from typing import Dict, Any, List, Union, TypedDict
import logging


class ExplanationContext(TypedDict, total=False):
    """Type definition for the context dictionary passed to build_explanation."""
    primary_factor: str
    secondary_factors: List[str]
    mission_phase: str
    confidence: Union[int, float, str]


class ExplanationResult(TypedDict):
    """Type definition for the structured explanation result."""
    primary_factor: str
    secondary_factors: List[str]
    mission_phase_constraint: str
    confidence: float


logger: logging.Logger = logging.getLogger(__name__)


def build_explanation(context: ExplanationContext) -> ExplanationResult:
    """
    Construct a structured explanation for an anomaly decision.

    Synthesizes context from the policy engine, detection model, and mission phase
    to create a coherent narrative of why a specific action was recommended.

    Args:
        context (ExplanationContext): Context dictionary containing:
            - primary_factor: The main reason for the decision.
            - secondary_factors: List of contributing factors.
            - mission_phase: Current operational phase.
            - confidence: Model confidence score.

    Returns:
        ExplanationResult: A structured explanation object suitable for UI display
        or logging.
    """
    if not isinstance(context, dict):
        logger.error(
            "Invalid context passed to build_explanation: expected dict, got %s",
            type(context).__name__,
        )
        raise TypeError("context must be a dictionary")

    try:
        confidence: float = float(context.get("confidence", 0.0))
    except (TypeError, ValueError):
        logger.error(
            "Invalid confidence value in explanation context: %r",
            context.get("confidence"),
            exc_info=True,
        )
        raise ValueError("confidence must be a numeric value")

    return {
        "primary_factor": context.get(
            "primary_factor", "Policy-based anomaly decision"
        ),
        "secondary_factors": context.get("secondary_factors", []),
        "mission_phase_constraint": context.get("mission_phase", "UNKNOWN"),
        "confidence": confidence,
    }
