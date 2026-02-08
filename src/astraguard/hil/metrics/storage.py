"""Persistent metrics storage for AstraGuard HIL (Hardware-in-the-Loop) system.

This module provides functionality to store, retrieve, and compare latency metrics
collected during HIL testing runs. It handles both aggregated statistics and raw
measurement data, enabling performance analysis and regression detection.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, cast
from datetime import datetime

from astraguard.hil.metrics.latency import LatencyCollector


class MetricsStorage:
    """Manages persistent storage of latency metrics for HIL testing runs.

    This class provides methods to save latency measurements to disk, load previously
    saved metrics, compare performance between different runs, and retrieve recent
    test runs.

    Attributes:
        run_id (str): Unique identifier for the current testing run.
        metrics_dir (Path): Directory path where metrics for this run are stored.
    """

    def __init__(self, run_id: str, results_dir: str = "astraguard/hil/results") -> None:
        """
        Initialize metrics storage.

        Args:
            run_id (str): Unique identifier for this run.
            results_dir (str, optional): Base directory for results. Defaults to "astraguard/hil/results".
        """
        try:
            self.run_id = run_id
            self.metrics_dir = Path(results_dir) / run_id
            self.metrics_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logging.error(f"Failed to initialize MetricsStorage for run {run_id}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error initializing MetricsStorage for run {run_id}: {e}")
            raise

    def save_latency_stats(self, collector: LatencyCollector) -> Dict[str, str]:
        """
        Save aggregated and raw latency metrics to disk.

        Args:
            collector (LatencyCollector): LatencyCollector instance containing measurements to save.

        Returns:
            Dict[str, str]: Dictionary with paths to saved files, containing 'summary' and 'raw' keys
                pointing to the JSON summary and CSV raw data files respectively.
        """
        try:
            stats = collector.get_stats()
            summary = collector.get_summary()

            # Summary JSON with all statistics
            summary_dict = {
                "run_id": self.run_id,
                "timestamp": datetime.now().isoformat(),
                "total_measurements": len(collector.measurements),
                "measurement_types": summary.get("measurement_types", {}),
                "stats": stats,
                "stats_by_satellite": summary.get("stats_by_satellite", {}),
            }

            summary_path = self.metrics_dir / "latency_summary.json"
            summary_path.write_text(json.dumps(summary_dict, indent=2, default=str))

            # Raw CSV for external analysis
            csv_path = self.metrics_dir / "latency_raw.csv"
            collector.export_csv(str(csv_path))

            return {"summary": str(summary_path), "raw": str(csv_path)}
        except (OSError, PermissionError) as e:
            logging.error(f"Failed to save latency stats for run {self.run_id}: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error saving latency stats for run {self.run_id}: {e}")
            raise

    def get_run_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Load metrics from this run.

        Returns:
            Dict[str, Any] or None: Parsed metrics dictionary containing run statistics,
                or None if the metrics file is not found or cannot be loaded.
        """
        summary_path = self.metrics_dir / "latency_summary.json"
        if not summary_path.exists():
            return None

        try:
            content = summary_path.read_text()
            return cast(Dict[str, Any], json.loads(content))
        except (OSError, PermissionError, IsADirectoryError) as e:
            logging.error(f"Failed to read metrics file {summary_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from {summary_path}: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error loading metrics from {summary_path}: {e}")
            return None

    def compare_runs(self, other_run_id: str) -> Dict[str, Any]:
        """
        Compare latency performance between this run and a historical run.

        Calculates the delta (difference) in Mean and P95 latency for all
        common metrics available in both runs. Useful for regression testing.

        Args:
            other_run_id (str): ID of the historical run to compare against.

        Returns:
            Dict[str, Any]: A comparison report containing:
                - run1, run2 (str): IDs of compared runs.
                - metrics (Dict): Per-metric differences (diff_ms).
                - error (str, optional): Error message if loading fails.
        """
        other_storage = MetricsStorage(other_run_id)
        other_metrics = other_storage.get_run_metrics()

        if other_metrics is None:
            return {"error": f"Could not load metrics for run {other_run_id}", "metrics": {}}

        this_metrics = self.get_run_metrics()
        if this_metrics is None:
            return {"error": f"Could not load metrics for run {self.run_id}", "metrics": {}}

        comparison: Dict[str, Any] = {
            "run1": self.run_id,
            "run2": other_run_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }

        # Compare each metric type
        this_stats = this_metrics.get("stats", {})
        other_stats = other_metrics.get("stats", {})

        for metric_type in set(list(this_stats.keys()) + list(other_stats.keys())):
            this_data = this_stats.get(metric_type, {})
            other_data = other_stats.get(metric_type, {})

            if not this_data or not other_data:
                continue

            comparison["metrics"][metric_type] = {
                "this_mean_ms": this_data.get("mean_ms", 0),
                "other_mean_ms": other_data.get("mean_ms", 0),
                "diff_ms": this_data.get("mean_ms", 0) - other_data.get("mean_ms", 0),
                "this_p95_ms": this_data.get("p95_ms", 0),
                "other_p95_ms": other_data.get("p95_ms", 0),
            }

        return comparison

    @staticmethod
    def get_recent_runs(
        results_dir: str = "astraguard/hil/results", limit: int = 10
    ) -> List[str]:
        """
        Get recent metric runs.

        Args:
            results_dir (str, optional): Base results directory. Defaults to "astraguard/hil/results".
            limit (int, optional): Maximum number of runs to return. Defaults to 10.

        Returns:
            list: List of recent run IDs, sorted by most recent first.
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            return []

        # Find directories with latency metrics
        runs = []
        for run_dir in sorted(results_path.iterdir(), reverse=True):
            if run_dir.is_dir() and (run_dir / "latency_summary.json").exists():
                runs.append(run_dir.name)
                if len(runs) >= limit:
                    break

        return runs
