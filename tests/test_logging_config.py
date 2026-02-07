"""
Unit tests for AstraGuard Structured Logging Module
"""

import pytest
import logging
import sys
import json
import asyncio
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
from pathlib import Path
import structlog

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from astraguard.logging_config import (
    setup_json_logging,
    get_logger,
    LogContext,
    log_request,
    log_error,
    log_detection,
    log_circuit_breaker_event,
    log_retry_event,
    log_recovery_action,
    log_performance_metric,
    async_log_request,
    async_log_error,
    async_log_detection,
    set_log_level,
    clear_context,
    bind_context,
    unbind_context,
    _cached_get_secret
)


class TestLoggingConfig:
    """Test suite for logging_config module"""

    def setup_method(self):
        """Setup test fixtures"""
        # Clear any existing context
        structlog.contextvars.clear_contextvars()
        # Reset logging
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.INFO)

    def teardown_method(self):
        """Cleanup after each test"""
        structlog.contextvars.clear_contextvars()
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.INFO)

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    @patch('astraguard.logging_config.logging.getLogger')
    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_setup_json_logging_success(self, mock_bind_context, mock_get_logger, mock_structlog_configure, mock_get_secret):
        """Test successful JSON logging setup"""
        mock_get_secret.side_effect = lambda key, default=None: {
            'environment': 'production',
            'app_version': '1.0.0'
        }.get(key, default)

        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        setup_json_logging(log_level="DEBUG", service_name="test-service")

        # Verify structlog configuration was called
        mock_structlog_configure.assert_called_once()
        # Verify context binding
        mock_bind_context.assert_called_once_with(
            service="test-service",
            environment="production",
            version="1.0.0"
        )
        # Verify root logger setup
        mock_root_logger.setLevel.assert_called_once_with(logging.DEBUG)
        mock_root_logger.addHandler.assert_called_once()

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.logging.basicConfig')
    def test_setup_json_logging_invalid_log_level(self, mock_basic_config, mock_get_secret):
        """Test setup with invalid log level falls back gracefully"""
        mock_get_secret.return_value = "production"

        # Should not raise, but fall back to basic logging
        setup_json_logging(log_level="INVALID")

        mock_basic_config.assert_called_once()

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    def test_setup_json_logging_fallback_on_import_error(self, mock_structlog_configure, mock_get_secret):
        """Test fallback to basic logging on structlog import error"""
        mock_get_secret.return_value = "production"
        mock_structlog_configure.side_effect = ImportError("structlog not available")

        with patch('astraguard.logging_config.logging.basicConfig') as mock_basic_config:
            setup_json_logging()

            mock_basic_config.assert_called_once_with(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
            )

    @patch('astraguard.logging_config._cached_get_secret')
    @patch('astraguard.logging_config.structlog.configure')
    def test_setup_json_logging_fallback_on_general_error(self, mock_structlog_configure, mock_get_secret):
        """Test fallback on general setup error"""
        mock_get_secret.return_value = "production"
        mock_structlog_configure.side_effect = Exception("Unexpected error")

        with patch('astraguard.logging_config.logging.basicConfig') as mock_basic_config:
            setup_json_logging()

            mock_basic_config.assert_called_once()

    @patch('astraguard.logging_config.structlog.get_logger')
    def test_get_logger(self, mock_get_logger):
        """Test get_logger function"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        result = get_logger("test_module")

        mock_get_logger.assert_called_once_with("test_module")
        assert result == mock_logger

    def test_log_context_manager(self):
        """Test LogContext context manager"""
        mock_logger = MagicMock()
        bound_logger = MagicMock()
        mock_logger.bind.return_value = bound_logger
        context = {"test_key": "test_value"}

        with LogContext(mock_logger, **context):
            # Verify bind was called
            mock_logger.bind.assert_called_once_with(**context)

        # Verify error logging on exception
        mock_logger.reset_mock()
        bound_logger.reset_mock()
        mock_logger.bind.return_value = bound_logger
        try:
            with LogContext(mock_logger, **context):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should have logged the error on the bound logger
        bound_logger.error.assert_called_once()
        call_args = bound_logger.error.call_args
        assert call_args[0][0] == "context_error"
        assert "error_type" in call_args[1]
        assert "error_message" in call_args[1]

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_bind_context(self, mock_bind):
        """Test bind_context function"""
        bind_context(key1="value1", key2="value2")
        mock_bind.assert_called_once_with(key1="value1", key2="value2")

    @patch('astraguard.logging_config.structlog.contextvars.unbind_contextvars')
    def test_unbind_context(self, mock_unbind):
        """Test unbind_context function"""
        unbind_context("key1", "key2")
        mock_unbind.assert_called_once_with("key1", "key2")

    @patch('astraguard.logging_config.structlog.contextvars.clear_contextvars')
    def test_clear_context(self, mock_clear):
        """Test clear_context function"""
        clear_context()
        mock_clear.assert_called_once()

    @patch('astraguard.logging_config.logging.getLogger')
    def test_set_log_level_valid(self, mock_get_logger):
        """Test set_log_level with valid level"""
        mock_root_logger = MagicMock()
        mock_get_logger.return_value = mock_root_logger

        set_log_level("DEBUG")

        mock_root_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_set_log_level_invalid(self):
        """Test set_log_level with invalid level"""
        with patch('builtins.print') as mock_print:
            set_log_level("INVALID")

            mock_print.assert_called_once()
            assert "Warning: Failed to set log level" in mock_print.call_args[0][0]

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_request(self, mock_bind):
        """Test log_request function"""
        mock_logger = MagicMock()

        log_request(
            mock_logger,
            method="GET",
            endpoint="/api/test",
            status=200,
            duration_ms=150.5,
            user_id="123"
        )

        mock_logger.info.assert_called_once_with(
            "http_request",
            method="GET",
            endpoint="/api/test",
            status=200,
            duration_ms=150.5,
            user_id="123"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_error(self, mock_bind):
        """Test log_error function"""
        mock_logger = MagicMock()
        test_error = ValueError("Test error")

        log_error(
            mock_logger,
            error=test_error,
            context="Database connection failed",
            user_id="123"
        )

        mock_logger.error.assert_called_once_with(
            "Database connection failed",
            error_type="ValueError",
            error_message="Test error",
            exc_info=True,
            user_id="123"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_detection(self, mock_bind):
        """Test log_detection function"""
        mock_logger = MagicMock()

        log_detection(
            mock_logger,
            severity="HIGH",
            detected_type="thermal_fault",
            confidence=0.95,
            sensor_id="temp_01"
        )

        mock_logger.info.assert_called_once_with(
            "anomaly_detected",
            severity="HIGH",
            type="thermal_fault",
            confidence=0.95,
            sensor_id="temp_01"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_circuit_breaker_event(self, mock_bind):
        """Test log_circuit_breaker_event function"""
        mock_logger = MagicMock()

        log_circuit_breaker_event(
            mock_logger,
            event="opened",
            breaker_name="api_circuit",
            state="OPEN",
            reason="timeout"
        )

        mock_logger.warning.assert_called_once_with(
            "circuit_breaker_event",
            event="opened",
            breaker="api_circuit",
            state="OPEN",
            reason="timeout"
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_retry_event(self, mock_bind):
        """Test log_retry_event function"""
        mock_logger = MagicMock()

        # Test retrying status
        log_retry_event(
            mock_logger,
            endpoint="/api/retry",
            attempt=2,
            status="retrying",
            delay_ms=1000.0
        )

        mock_logger.info.assert_called_once_with(
            "retry_event",
            endpoint="/api/retry",
            attempt=2,
            status="retrying",
            delay_ms=1000.0
        )

        # Test exhausted status
        mock_logger.reset_mock()
        log_retry_event(
            mock_logger,
            endpoint="/api/retry",
            attempt=3,
            status="exhausted"
        )

        mock_logger.warning.assert_called_once_with(
            "retry_event",
            endpoint="/api/retry",
            attempt=3,
            status="exhausted",
            delay_ms=None
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_recovery_action(self, mock_bind):
        """Test log_recovery_action function"""
        mock_logger = MagicMock()

        log_recovery_action(
            mock_logger,
            action_type="restart_service",
            status="completed",
            component="api_gateway",
            duration_ms=5000.0
        )

        mock_logger.info.assert_called_once_with(
            "recovery_action",
            action="restart_service",
            status="completed",
            component="api_gateway",
            duration_ms=5000.0
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_performance_metric_no_alert(self, mock_bind):
        """Test log_performance_metric without alert"""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="response_time",
            value=120.5,
            unit="ms",
            threshold=200.0
        )

        mock_logger.info.assert_called_once_with(
            "performance_metric",
            metric="response_time",
            value=120.5,
            unit="ms",
            threshold=200.0,
            alert=False
        )

    @patch('astraguard.logging_config.structlog.contextvars.bind_contextvars')
    def test_log_performance_metric_with_alert(self, mock_bind):
        """Test log_performance_metric with alert"""
        mock_logger = MagicMock()

        log_performance_metric(
            mock_logger,
            metric_name="response_time",
            value=250.0,
            unit="ms",
            threshold=200.0
        )

        mock_logger.warning.assert_called_once_with(
            "performance_metric",
            metric="response_time",
            value=250.0,
            unit="ms",
            threshold=200.0,
            alert=True
        )

    @pytest.mark.asyncio
    async def test_async_log_request(self):
        """Test async_log_request function"""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.log_request') as mock_log_request:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_request(
                    mock_logger,
                    method="POST",
                    endpoint="/api/async",
                    status=201,
                    duration_ms=200.0
                )

                mock_to_thread.assert_called_once()
                # Verify the function was called with correct args
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_request
                assert call_args[1] == mock_logger
                assert call_args[2] == "POST"
                assert call_args[3] == "/api/async"
                assert call_args[4] == 201
                assert call_args[5] == 200.0

    @pytest.mark.asyncio
    async def test_async_log_error(self):
        """Test async_log_error function"""
        mock_logger = MagicMock()
        test_error = RuntimeError("Async error")

        with patch('astraguard.logging_config.log_error') as mock_log_error:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_error(
                    mock_logger,
                    error=test_error,
                    context="Async operation failed"
                )

                mock_to_thread.assert_called_once()
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_error
                assert call_args[1] == mock_logger
                assert call_args[2] == test_error
                assert call_args[3] == "Async operation failed"

    @pytest.mark.asyncio
    async def test_async_log_detection(self):
        """Test async_log_detection function"""
        mock_logger = MagicMock()

        with patch('astraguard.logging_config.log_detection') as mock_log_detection:
            with patch('astraguard.logging_config.asyncio.to_thread') as mock_to_thread:
                mock_to_thread.return_value = None

                await async_log_detection(
                    mock_logger,
                    severity="CRITICAL",
                    detected_type="power_failure",
                    confidence=0.99
                )

                mock_to_thread.assert_called_once()
                call_args = mock_to_thread.call_args[0]
                assert call_args[0] == mock_log_detection
                assert call_args[1] == mock_logger
                assert call_args[2] == "CRITICAL"
                assert call_args[3] == "power_failure"
                assert call_args[4] == 0.99

    @patch('astraguard.logging_config.get_secret')
    def test_cached_get_secret_success(self, mock_get_secret):
        """Test _cached_get_secret success"""
        mock_get_secret.return_value = "test_value"

        # Clear cache
        _cached_get_secret.cache_clear()

        result1 = _cached_get_secret("test_key", "default")
        result2 = _cached_get_secret("test_key", "default")

        assert result1 == "test_value"
        assert result2 == "test_value"
        # Should only call get_secret once due to caching
        mock_get_secret.assert_called_once_with("test_key", "default")

    @patch('astraguard.logging_config.get_secret')
    def test_cached_get_secret_exception(self, mock_get_secret):
        """Test _cached_get_secret with exception"""
        mock_get_secret.side_effect = Exception("Secret not found")

        # Clear cache
        _cached_get_secret.cache_clear()

        result = _cached_get_secret("missing_key", "fallback")

        assert result == "fallback"
        mock_get_secret.assert_called_once_with("missing_key", "fallback")

    def test_module_imports(self):
        """Test that all expected functions are importable"""
        # This test ensures the module can be imported without errors
        assert callable(setup_json_logging)
        assert callable(get_logger)
        assert callable(LogContext)
        assert callable(log_request)
        assert callable(log_error)
        assert callable(log_detection)
        assert callable(log_circuit_breaker_event)
        assert callable(log_retry_event)
        assert callable(log_recovery_action)
        assert callable(log_performance_metric)
        assert callable(async_log_request)
        assert callable(async_log_error)
        assert callable(async_log_detection)
        assert callable(set_log_level)
        assert callable(clear_context)
        assert callable(bind_context)
        assert callable(unbind_context)
        assert callable(_cached_get_secret)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
