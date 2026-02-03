"""Test result persistence and retrieval."""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ResultStorage:
    """Manages persistent storage and retrieval of test results."""

    def __init__(self, results_dir: str = "astraguard/hil/results"):
        """
        Initialize result storage.

        Args:
            results_dir: Directory for result files
        """
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def save_scenario_result(
        self, scenario_name: str, result: Dict[str, Any]
    ) -> str:
        """
        Save individual scenario result to file asynchronously.

        Args:
            scenario_name: Name of scenario (without .yaml)
            result: Execution result dict

        Returns:
            Path to saved result file
        """
        if not scenario_name or not isinstance(scenario_name, str):
            raise ValueError(f"Invalid scenario_name: {scenario_name}")
        
        if not isinstance(result, dict):
            raise ValueError(f"Result must be a dictionary, got {type(result)}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scenario_name}_{timestamp}.json"
        filepath = self.results_dir / filename

        # Ensure result has metadata
        result_with_metadata = {
            "scenario_name": scenario_name,
            "timestamp": datetime.now().isoformat(),
            **result,
        }

        try:
            filepath.write_text(json.dumps(result_with_metadata, indent=2, default=str))
            logger.info(f"Saved scenario result: {filepath}")
            return str(filepath)
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to write result file {filepath}: {e}")
            raise
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize result data for {scenario_name}: {e}")
            raise

    async def get_scenario_results(
        self, scenario_name: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent results for a specific scenario asynchronously.

        Args:
            scenario_name: Name of scenario
            limit: Maximum results to return

        Returns:
            List of result dicts (newest first)
        """
        if not scenario_name or not isinstance(scenario_name, str):
            logger.warning(f"Invalid scenario_name: {scenario_name}")
            return []
        
        if limit <= 0:
            logger.warning(f"Invalid limit: {limit}")
            return []

        results = []
        pattern = f"{scenario_name}_*.json"
        result_files = sorted(self.results_dir.glob(pattern), reverse=True)[:limit]

        for result_file in result_files:
            try:
                result_data = await asyncio.to_thread(json.loads, result_file.read_text())
                results.append(result_data)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to read result file {result_file.name}: {e}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Corrupted result file {result_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading result {result_file.name}: {e}")

        return results

    def get_recent_campaigns(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent campaign summaries.

        Args:
            limit: Maximum campaigns to return

        Returns:
            List of campaign summary dicts (newest first)
        """
        if limit <= 0:
            logger.warning(f"Invalid limit: {limit}")
            return []

        campaigns = []
        campaign_files = sorted(
            self.results_dir.glob("campaign_*.json"), reverse=True
        )[:limit]

        for campaign_file in campaign_files:
            try:
                campaign_data = json.loads(campaign_file.read_text())
                campaigns.append(campaign_data)
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to read campaign file {campaign_file.name}: {e}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"Corrupted campaign file {campaign_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading campaign {campaign_file.name}: {e}")

        return campaigns

    def get_campaign_summary(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve specific campaign by ID.

        Args:
            campaign_id: Campaign timestamp ID (YYYYMMDD_HHMMSS)

        Returns:
            Campaign summary dict or None if not found
        """
        if not campaign_id or not isinstance(campaign_id, str):
            logger.warning(f"Invalid campaign_id: {campaign_id}")
            return None

        campaign_file = self.results_dir / f"campaign_{campaign_id}.json"
        if not campaign_file.exists():
            return None

        try:
            return json.loads(campaign_file.read_text())
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to read campaign {campaign_id}: {e}")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Corrupted campaign file {campaign_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading campaign {campaign_id}: {e}")
            return None

    def get_result_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics across all results.

        Returns:
            Dict with statistics
        """
        campaigns = self.get_recent_campaigns(limit=999)
        if not campaigns:
            return {
                "total_campaigns": 0,
                "total_scenarios": 0,
                "avg_pass_rate": 0.0,
            }

        total_campaigns = len(campaigns)
        total_scenarios = sum(c.get("total_scenarios", 0) for c in campaigns)
        total_passed = sum(c.get("passed", 0) for c in campaigns)
        avg_pass_rate = total_passed / total_scenarios if total_scenarios > 0 else 0.0

        return {
            "total_campaigns": total_campaigns,
            "total_scenarios": total_scenarios,
            "total_passed": total_passed,
            "avg_pass_rate": avg_pass_rate,
        }

    def clear_results(self, older_than_days: int = 30) -> int:
        """
        Remove old result files.

        Args:
            older_than_days: Delete files older than this many days

        Returns:
            Number of files deleted
        """
        if older_than_days <= 0:
            logger.warning(f"Invalid age threshold: {older_than_days}")
            return 0

        from time import time

        cutoff_time = time() - (older_than_days * 86400)
        deleted_count = 0

        for result_file in self.results_dir.glob("*.json"):
            try:
                if result_file.stat().st_mtime < cutoff_time:
                    result_file.unlink()
                    deleted_count += 1
            except (OSError, IOError, PermissionError) as e:
                logger.warning(f"Failed to delete file {result_file.name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error deleting file {result_file.name}: {e}")

        logger.info(f"Cleanup completed: deleted {deleted_count} files older than {older_than_days} days")
        return deleted_count
