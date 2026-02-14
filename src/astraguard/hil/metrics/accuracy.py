"""Ground-truth accuracy metrics for agent classification validation."""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from collections import defaultdict
import bisect
import logging


logger = logging.getLogger(__name__)


class FaultState(str, Enum):
    """Fault states for ground truth."""
    NOMINAL = "nominal"
    FAULTY = "faulty"


@dataclass
class GroundTruthEvent:
    """Ground truth event during scenario."""

    timestamp_s: float
    satellite_id: str
    expected_fault_type: Optional[str]  # None = nominal
    confidence: float = 1.0  # Ground truth confidence (always 1.0 in scenarios)


@dataclass
class AgentClassification:
    """Agent classification attempt."""

    timestamp_s: float
    satellite_id: str
    predicted_fault: Optional[str]  # None = nominal prediction
    confidence: float
    is_correct: bool


class AccuracyCollector:
    """Validates agent classification accuracy against scenario ground truth."""

    def __init__(self):
        """Initialize accuracy collector."""
        self.ground_truth_events: List[GroundTruthEvent] = []
        self.agent_classifications: List[AgentClassification] = []
        # Precomputed sorted ground truth events per satellite for efficient lookups
        self._ground_truth_by_sat: Dict[str, List[GroundTruthEvent]] = defaultdict(list)

    def record_ground_truth(
        self,
        sat_id: str,
        scenario_time_s: float,
        fault_type: Optional[str],
        confidence: float = 1.0,
    ) -> None:
        """
        Record ground truth for satellite at time.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time
            fault_type: Expected fault type (None = nominal)
            confidence: Ground truth confidence (always 1.0)
        """
        try:
            event = GroundTruthEvent(
                timestamp_s=scenario_time_s,
                satellite_id=sat_id,
                expected_fault_type=fault_type,
                confidence=confidence,
            )
            self.ground_truth_events.append(event)
            # Add to precomputed sorted list
            self._ground_truth_by_sat[sat_id].append(event)
            # Keep sorted by timestamp
            self._ground_truth_by_sat[sat_id].sort(key=lambda e: e.timestamp_s)
        except (TypeError, ValueError) as e:
            logger.exception("Failed to record ground truth event")
            raise

    def record_agent_classification(
        self,
        sat_id: str,
        scenario_time_s: float,
        predicted_fault: Optional[str],
        confidence: float,
        is_correct: bool,
    ) -> None:
        """
        Record agent classification attempt.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time
            predicted_fault: Predicted fault type (None = nominal)
            confidence: Agent's confidence in prediction
            is_correct: Whether prediction matches ground truth
        """
        try:
            classification = AgentClassification(
                timestamp_s=scenario_time_s,
                satellite_id=sat_id,
                predicted_fault=predicted_fault,
                confidence=confidence,
                is_correct=is_correct,
            )
            self.agent_classifications.append(classification)
        except (TypeError, ValueError) as e:
            logger.exception("Failed to record agent classification")
            raise

    def get_accuracy_stats(self) -> Dict[str, Any]:
        """
        Calculate comprehensive classification accuracy statistics.
        """
        if not self.agent_classifications:
            return {
                "total_classifications": 0,
                "correct_classifications": 0,
                "overall_accuracy": 0.0,
                "by_fault_type": {},
                "confidence_mean": 0.0,
                "confidence_std": 0.0,
            }

        try:
            total = len(self.agent_classifications)
            correct = sum(1 for c in self.agent_classifications if c.is_correct)

            # Per-fault-type breakdown
            by_fault = self._calculate_per_fault_stats()

            # Confidence statistics
            confidences = [c.confidence for c in self.agent_classifications]
            confidence_mean = float(np.mean(confidences))
            confidence_std = float(np.std(confidences))

            return {
                "total_classifications": total,
                "correct_classifications": correct,
                "overall_accuracy": correct / total if total > 0 else 0.0,
                "by_fault_type": by_fault,
                "confidence_mean": confidence_mean,
                "confidence_std": confidence_std,
            }
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.exception("Error while computing accuracy statistics")
            raise

    def _calculate_per_fault_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate precision, recall, F1 per fault type.
        """
        try:
            fault_types = set()
            for c in self.agent_classifications:
                if c.predicted_fault:
                    fault_types.add(c.predicted_fault)
            for e in self.ground_truth_events:
                if e.expected_fault_type:
                    fault_types.add(e.expected_fault_type)

            stats = {}

            for fault_type in sorted(fault_types):
                tp = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type and c.is_correct
                )

                fp = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type and not c.is_correct
                )

                fn = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault != fault_type
                    and c.is_correct is False
                    and self._find_ground_truth_fault(
                        c.satellite_id, c.timestamp_s
                    )
                    == fault_type
                )

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = (
                    2 * (precision * recall) / (precision + recall)
                    if (precision + recall) > 0
                    else 0.0
                )

                predictions = [
                    c
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type
                ]

                stats[fault_type] = {
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "true_positives": tp,
                    "false_positives": fp,
                    "false_negatives": fn,
                    "total_predictions": len(predictions),
                    "correct_predictions": tp,
                    "avg_confidence": (
                        float(np.mean([c.confidence for c in predictions]))
                        if predictions
                        else 0.0
                    ),
                }

            return stats
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.exception("Error while calculating per-fault statistics")
            raise

    def get_stats_by_satellite(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate accuracy statistics per satellite.
        """
        try:
            by_satellite = defaultdict(list)

            for c in self.agent_classifications:
                by_satellite[c.satellite_id].append(c)

            stats = {}
            for sat_id, classifications in by_satellite.items():
                total = len(classifications)
                correct = sum(1 for c in classifications if c.is_correct)

                stats[sat_id] = {
                    "total_classifications": total,
                    "correct_classifications": correct,
                    "accuracy": correct / total if total > 0 else 0.0,
                    "avg_confidence": (
                        float(np.mean([c.confidence for c in classifications]))
                        if classifications
                        else 0.0
                    ),
                }

            return stats
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.exception("Error while calculating per-satellite statistics")
            raise

    def get_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """
        Build confusion matrix of predicted vs actual fault types.
        """
        confusion = defaultdict(lambda: defaultdict(int))

        try:
            for c in self.agent_classifications:
                actual_fault = self._find_ground_truth_fault(
                    c.satellite_id, c.timestamp_s
                )

                predicted = c.predicted_fault or "nominal"
                actual = actual_fault or "nominal"

                confusion[predicted][actual] += 1

            return dict(confusion)
        except (TypeError, ValueError) as e:
            logger.exception("Failed while building confusion matrix")
            raise

    def export_csv(self, filename: str) -> None:
        """
        Export classifications to CSV for analysis.
        """
        import csv
        from pathlib import Path

        try:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)

            with open(filename, "w", newline="") as f:
                fieldnames = [
                    "timestamp_s",
                    "satellite_id",
                    "predicted_fault",
                    "confidence",
                    "is_correct",
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for c in self.agent_classifications:
                    writer.writerow(
                        {
                            "timestamp_s": c.timestamp_s,
                            "satellite_id": c.satellite_id,
                            "predicted_fault": c.predicted_fault or "nominal",
                            "confidence": c.confidence,
                            "is_correct": c.is_correct,
                        }
                    )
        except (OSError, IOError, TypeError, ValueError) as e:
            logger.exception("Failed to export CSV file")
            raise

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive accuracy summary.
        """
        try:
            return {
                "total_events": len(self.ground_truth_events),
                "total_classifications": len(self.agent_classifications),
                "stats": self.get_accuracy_stats(),
                "stats_by_satellite": self.get_stats_by_satellite(),
                "confusion_matrix": self.get_confusion_matrix(),
            }
        except (TypeError, ValueError) as e:
            logger.exception("Failed to generate summary")
            raise

    def _find_ground_truth_fault(
        self, sat_id: str, timestamp_s: float
    ) -> Optional[str]:
        """
        Find the ground truth fault type for a satellite at a given timestamp.
        """
        if sat_id not in self._ground_truth_by_sat:
            return None

        events = self._ground_truth_by_sat[sat_id]
        if not events:
            return None

        try:
            idx = bisect.bisect_right(
                events, timestamp_s, key=lambda e: e.timestamp_s
            ) - 1

            if idx < 0:
                return None

            return events[idx].expected_fault_type
        except (TypeError, ValueError) as e:
            logger.exception(
                "Binary search failed while finding ground truth fault"
            )
            raise

    def reset(self) -> None:
        """Clear all data."""
        self.ground_truth_events.clear()
        self.agent_classifications.clear()
        self._ground_truth_by_sat.clear()

    def __len__(self) -> int:
        """Return number of classifications."""
        return len(self.agent_classifications)
