"""
Unit tests for src/api/service.py

Tests cover FastAPI endpoints, helper functions, and core functionality
with mocking for external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import json
from fastapi.testclient import TestClient
from fastapi import HTTPException
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api.service import (
    app,
    check_chaos_injection,
    inject_chaos_fault,
    create_response,
    process_telemetry_batch,
    cleanup_expired_faults,
    _check_credential_security,
    initialize_components,
    _process_telemetry
)
from api.models import TelemetryInput, TelemetryBatch
from core.auth import UserCreateRequest, UserResponse, LoginRequest, TokenResponse


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_dependencies():
    """Mock external dependencies."""
    with patch('api.service.state_machine') as mock_state_machine, \
         patch('api.service.policy_loader') as mock_policy_loader, \
         patch('api.service.phase_aware_handler') as mock_handler, \
         patch('api.service.memory_store') as mock_memory_store, \
         patch('api.service.predictive_engine') as mock_predictive, \
         patch('api.service.get_health_monitor') as mock_health_monitor, \
         patch('api.service.get_auth_manager') as mock_auth_manager, \
         patch('api.service.get_api_key') as mock_get_api_key, \
         patch('api.service.require_operator') as mock_require_operator, \
         patch('api.service.require_admin') as mock_require_admin, \
         patch('api.service.require_phase_update') as mock_require_phase_update, \
         patch('api.service.require_analyst') as mock_require_analyst, \
         patch('api.service.get_current_user') as mock_get_current_user:

        # Configure mocks
        mock_state_machine.get_current_phase.return_value.value = "NOMINAL_OPS"
        mock_memory_store.get_stats.return_value = {
            'total_events': 100,
            'critical_events': 5,
            'avg_age_hours': 24.5,
            'max_recurrence': 3
        }
        mock_health_monitor.return_value.get_all_health.return_value = {
            'anomaly_detector': {'status': 'HEALTHY', 'timestamp': datetime.now()},
            'memory_store': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }

        yield {
            'state_machine': mock_state_machine,
            'policy_loader': mock_policy_loader,
            'handler': mock_handler,
            'memory_store': mock_memory_store,
            'predictive': mock_predictive,
            'health_monitor': mock_health_monitor,
            'auth_manager': mock_auth_manager,
            'get_api_key': mock_get_api_key,
            'require_operator': mock_require_operator,
            'require_admin': mock_require_admin,
            'require_phase_update': mock_require_phase_update,
            'require_analyst': mock_require_analyst,
            'get_current_user': mock_get_current_user
        }


class TestHelperFunctions:
    """Test helper functions."""

    def test_check_chaos_injection_active(self):
        """Test chaos injection check when fault is active."""
        from api.service import active_faults
        active_faults['test_fault'] = time.time() + 60  # Active for 60 seconds

        assert check_chaos_injection('test_fault') is True

    def test_check_chaos_injection_expired(self):
        """Test chaos injection check when fault has expired."""
        from api.service import active_faults
        active_faults['test_fault'] = time.time() - 60  # Expired 60 seconds ago

        assert check_chaos_injection('test_fault') is False
        assert 'test_fault' not in active_faults  # Should be cleaned up

    def test_check_chaos_injection_inactive(self):
        """Test chaos injection check when fault is not active."""
        assert check_chaos_injection('nonexistent_fault') is False

    def test_inject_chaos_fault(self):
        """Test injecting a chaos fault."""
        from api.service import active_faults
        result = inject_chaos_fault('test_fault', 30)

        assert result['status'] == 'injected'
        assert result['fault'] == 'test_fault'
        assert 'expires_at' in result
        assert 'test_fault' in active_faults

    def test_create_response(self):
        """Test creating standardized API response."""
        response = create_response("success", {"data": "test"}, custom_field="value")

        assert response['status'] == 'success'
        assert 'timestamp' in response
        assert response['data'] == 'test'
        assert response['custom_field'] == 'value'

    @patch('api.service.anomaly_detector')
    @patch('api.service.AnomalyEvent')
    def test_process_telemetry_batch(self, mock_anomaly_event, mock_detector):
        """Test processing a batch of telemetry data."""
        mock_detector.detect_anomaly.return_value = 0.8  # Anomaly detected

        telemetry_list = [
            {'metric': 'temp', 'value': 85.0},
            {'metric': 'voltage', 'value': 3.5}
        ]

        result = process_telemetry_batch(telemetry_list)

        assert result['processed'] == 2
        assert result['anomalies_detected'] == 2  # Both detected as anomalies

    def test_cleanup_expired_faults(self):
        """Test cleanup of expired chaos faults."""
        from api.service import active_faults
        current_time = time.time()
        active_faults['expired'] = current_time - 10
        active_faults['active'] = current_time + 60

        cleanup_expired_faults()

        assert 'expired' not in active_faults
        assert 'active' in active_faults


class TestCredentialSecurity:
    """Test credential security checks."""

    @patch('api.service.get_secret')
    def test_check_credential_security_configured(self, mock_get_secret):
        """Test credential security check when properly configured."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'testuser',
            'METRICS_PASSWORD': 'strongpassword123'
        }.get(key)

        # Should not raise any exceptions
        _check_credential_security()

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_missing(self, mock_print, mock_get_secret):
        """Test credential security check when credentials are missing."""
        mock_get_secret.return_value = None

        _check_credential_security()

        # Should print warning messages
        mock_print.assert_called()

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_weak(self, mock_print, mock_get_secret):
        """Test credential security check with weak credentials."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'admin',
            'METRICS_PASSWORD': 'admin'
        }.get(key)

        _check_credential_security()

        # Should print security warnings
        mock_print.assert_called()


class TestFastAPIEndpoints:
    """Test FastAPI endpoints."""

    def test_root_endpoint(self, client):
        """Test root health check endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'version' in data
        assert 'timestamp' in data

    @patch('api.service.get_health_monitor')
    @patch('api.service.state_machine')
    @patch('api.service.start_time', 1000000000)  # Mock start time
    def test_health_check_endpoint(self, mock_state_machine, mock_health_monitor, client):
        """Test health check endpoint."""
        mock_health_monitor.return_value.get_all_health.return_value = {
            'component1': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }
        mock_state_machine.get_current_phase.return_value.value = 'NOMINAL_OPS'

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'uptime_seconds' in data
        assert 'mission_phase' in data
        assert 'components_status' in data

    @patch('api.service.OBSERVABILITY_ENABLED', True)
    @patch('api.service.get_metrics_text')
    @patch('api.service.get_metrics_content_type')
    @patch('api.service.get_current_username')
    def test_metrics_endpoint(self, mock_auth, mock_content_type, mock_text, client):
        """Test metrics endpoint."""
        mock_auth.return_value = 'testuser'
        mock_text.return_value = 'metrics_data'
        mock_content_type.return_value = 'text/plain'

        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.text == 'metrics_data'

    @patch('api.service.OBSERVABILITY_ENABLED', False)
    def test_metrics_endpoint_disabled(self, client):
        """Test metrics endpoint when observability is disabled."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.json() == {"error": "Observability not enabled"}

    @patch('api.service.get_api_key')
    def test_get_latest_telemetry_no_data(self, mock_api_key, client):
        """Test getting latest telemetry when no data exists."""
        mock_api_key.return_value = Mock()

        response = client.get("/api/v1/telemetry/latest")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'no_data'
        assert data['data'] is None

    @patch('api.service.get_api_key')
    @patch('api.service.latest_telemetry_data')
    def test_get_latest_telemetry_with_data(self, mock_latest, mock_api_key, client):
        """Test getting latest telemetry when data exists."""
        mock_api_key.return_value = Mock()
        mock_latest = {
            'data': {'voltage': 8.0},
            'timestamp': datetime.now()
        }

        # Patch the global variable
        import api.service
        api.service.latest_telemetry_data = mock_latest

        response = client.get("/api/v1/telemetry/latest")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['voltage'] == 8.0

    @patch('api.service.get_api_key')
    @patch('api.service.memory_store')
    def test_get_memory_stats(self, mock_memory_store, mock_api_key, client):
        """Test memory stats endpoint."""
        mock_api_key.return_value = Mock()
        mock_memory_store.get_stats.return_value = {
            'total_events': 50,
            'critical_events': 2,
            'avg_age_hours': 12.5,
            'max_recurrence': 1
        }

        response = client.get("/api/v1/memory/stats")

        assert response.status_code == 200
        data = response.json()
        assert data['total_events'] == 50
        assert data['critical_events'] == 2

    @patch('api.service.get_api_key')
    @patch('api.service.anomaly_history')
    def test_get_anomaly_history(self, mock_history, mock_api_key, client):
        """Test anomaly history endpoint."""
        mock_api_key.return_value = Mock()
        mock_history.__iter__.return_value = []  # Empty history

        response = client.get("/api/v1/history/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert 'count' in data
        assert 'anomalies' in data

    @patch('api.service.get_api_key')
    @patch('api.service.state_machine')
    @patch('api.service.phase_aware_handler')
    def test_get_phase(self, mock_handler, mock_state_machine, mock_api_key, client):
        """Test get phase endpoint."""
        mock_api_key.return_value = Mock()
        mock_state_machine.get_current_phase.return_value = Mock(value='NOMINAL_OPS')
        mock_state_machine.get_phase_description.return_value = 'Normal operations'
        mock_state_machine.get_phase_history.return_value = []
        mock_handler.get_phase_constraints.return_value = {'max_power': 100}

        response = client.get("/api/v1/phase")

        assert response.status_code == 200
        data = response.json()
        assert data['phase'] == 'NOMINAL_OPS'
        assert 'constraints' in data
        assert 'history' in data


class TestTelemetryProcessing:
    """Test telemetry processing functions."""

    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @pytest.mark.asyncio
    async def test_process_telemetry_normal(self, mock_state_machine, mock_memory_store,
                                          mock_handler, mock_classify, mock_detect):
        """Test processing normal telemetry (no anomaly)."""
        # Setup mocks
        mock_detect.return_value = (False, 0.1)  # No anomaly
        mock_classify.return_value = 'normal'
        mock_state_machine.get_current_phase.return_value.value = 'NOMINAL_OPS'

        telemetry = TelemetryInput(
            voltage=8.0,
            temperature=25.0,
            gyro=0.02,
            current=1.1,
            wheel_speed=5000,
            timestamp=datetime.now()
        )

        result = await _process_telemetry(telemetry, 0.0)

        assert result.is_anomaly is False
        assert result.anomaly_type == 'normal'
        assert result.mission_phase == 'NOMINAL_OPS'

    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @pytest.mark.asyncio
    async def test_process_telemetry_anomaly(self, mock_state_machine, mock_memory_store,
                                           mock_handler, mock_classify, mock_detect):
        """Test processing anomalous telemetry."""
        # Setup mocks
        mock_detect.return_value = (True, 0.9)  # Anomaly detected
        mock_classify.return_value = 'thermal_fault'

        decision = {
            'anomaly_type': 'thermal_fault',
            'severity_score': 0.9,
            'policy_decision': {
                'severity': 'HIGH',
                'escalation_level': 'MONITOR',
                'is_allowed': True,
                'allowed_actions': ['LOG', 'NOTIFY']
            },
            'mission_phase': 'NOMINAL_OPS',
            'recommended_action': 'THERMAL_REGULATION',
            'should_escalate_to_safe_mode': False,
            'detection_confidence': 0.85,
            'reasoning': 'High temperature detected',
            'recurrence_info': {'count': 1}
        }
        mock_handler.handle_anomaly.return_value = decision
        mock_state_machine.get_current_phase.return_value.value = 'NOMINAL_OPS'

        telemetry = TelemetryInput(
            voltage=8.0,
            temperature=85.0,  # High temperature
            gyro=0.02,
            current=1.1,
            wheel_speed=5000,
            timestamp=datetime.now()
        )

        result = await _process_telemetry(telemetry, 0.0)

        assert result.is_anomaly is True
        assert result.anomaly_type == 'thermal_fault'
        assert result.severity_level == 'HIGH'
        assert result.recommended_action == 'THERMAL_REGULATION'
        mock_memory_store.write.assert_called_once()


class TestAuthentication:
    """Test authentication endpoints."""

    @patch('api.service.get_auth_manager')
    def test_login_success(self, mock_auth_manager, client):
        """Test successful user login."""
        mock_auth_manager.return_value.authenticate_user.return_value = 'fake_token'

        login_data = {
            'username': 'testuser',
            'password': 'testpass'
        }

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['token_type'] == 'bearer'

    @patch('api.service.get_auth_manager')
    @patch('api.service.require_admin')
    def test_create_user(self, mock_require_admin, mock_auth_manager, client):
        """Test creating a new user."""
        mock_require_admin.return_value = Mock(id=1, username='admin')
        mock_user = Mock()
        mock_user.id = 2
        mock_user.username = 'newuser'
        mock_user.role.value = 'operator'
        mock_user.email = 'new@example.com'
        mock_user.created_at = datetime.now()
        mock_user.is_active = True
        mock_auth_manager.return_value.create_user.return_value = mock_user

        user_data = {
            'username': 'newuser',
            'password': 'securepass',
            'role': 'operator',
            'email': 'new@example.com'
        }

        response = client.post("/api/v1/auth/users", json=user_data)

        assert response.status_code == 200
        data = response.json()
        assert data['username'] == 'newuser'
        assert data['role'] == 'operator'


class TestChaosInjection:
    """Test chaos engineering features."""

    @patch('api.service.active_faults')
    @patch('time.sleep')
    @patch('api.service.require_operator')
    @patch('api.service._process_telemetry')
    def test_telemetry_with_network_latency(self, mock_process, mock_require_op,
                                          mock_sleep, mock_active_faults, client):
        """Test telemetry submission with network latency chaos injection."""
        mock_require_op.return_value = Mock()
        mock_process.return_value = Mock(is_anomaly=False, anomaly_score=0.1)
        mock_active_faults.__contains__.return_value = True
        mock_active_faults.__getitem__.return_value = time.time() + 60

        # Mock the check_chaos_injection to return True for network_latency
        with patch('api.service.check_chaos_injection', return_value=True):
            telemetry_data = {
                'voltage': 8.0,
                'temperature': 25.0,
                'gyro': 0.02,
                'current': 1.1,
                'wheel_speed': 5000
            }

            response = client.post("/api/v1/telemetry", json=telemetry_data)

            # Should succeed despite chaos injection
            assert response.status_code == 200
            mock_sleep.assert_called_with(2.0)  # Network latency delay

    @patch('api.service.require_operator')
    def test_telemetry_with_model_loader_failure(self, mock_require_op, client):
        """Test telemetry submission with model loader failure chaos injection."""
        mock_require_op.return_value = Mock()

        with patch('api.service.check_chaos_injection', return_value=True):
            telemetry_data = {
                'voltage': 8.0,
                'temperature': 25.0,
                'gyro': 0.02,
                'current': 1.1,
                'wheel_speed': 5000
            }

            # Patch to simulate model loader failure
            with patch('api.service.check_chaos_injection', side_effect=[False, True]):  # First False, second True
                response = client.post("/api/v1/telemetry", json=telemetry_data)

                # Should fail with 503 due to chaos injection
                assert response.status_code == 503
                assert "Chaos Injection: Model Loader Failed" in response.json()['detail']


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('api.service.require_operator')
    @patch('api.service._process_telemetry')
    def test_telemetry_processing_error(self, mock_process, mock_require_op, client):
        """Test handling of telemetry processing errors."""
        mock_require_op.return_value = Mock()
        mock_process.side_effect = Exception("Processing failed")

        telemetry_data = {
            'voltage': 8.0,
            'temperature': 25.0,
            'gyro': 0.02,
            'current': 1.1,
            'wheel_speed': 5000
        }

        response = client.post("/api/v1/telemetry", json=telemetry_data)

        assert response.status_code == 500
        assert "Anomaly detection failed" in response.json()['detail']

    @patch('api.service.get_api_key')
    @patch('api.service.state_machine')
    def test_phase_update_invalid_phase(self, mock_state_machine, mock_api_key, client):
        """Test phase update with invalid phase."""
        mock_api_key.return_value = Mock()
        mock_state_machine.set_phase.side_effect = ValueError("Invalid phase")

        phase_data = {'phase': 'INVALID_PHASE'}

        response = client.post("/api/v1/phase", json=phase_data)

        assert response.status_code == 400
        assert "Phase transition failed" in response.json()['detail']


if __name__ == "__main__":
    pytest.main([__file__])
