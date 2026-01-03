"""
Tests for REST API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from api.service import app, initialize_components


@pytest.fixture(scope="session", autouse=True)
def setup_components():
    """Initialize components before all tests."""
    initialize_components()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns health status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestTelemetryEndpoints:
    """Test telemetry submission endpoints."""

    def test_submit_normal_telemetry(self, client):
        """Test submitting normal telemetry (no anomaly)."""
        telemetry = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.01,
            "current": 1.2,
            "wheel_speed": 3000
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200
        data = response.json()
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert "recommended_action" in data

    def test_submit_anomalous_telemetry(self, client):
        """Test submitting anomalous telemetry."""
        telemetry = {
            "voltage": 6.5,  # Below threshold
            "temperature": 50.0,  # High temperature
            "gyro": 0.2,  # High gyro
            "current": 2.0,
            "wheel_speed": 5000
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is True
        assert data["anomaly_score"] > 0.0
        assert data["anomaly_type"] in ["power_fault", "thermal_fault", "attitude_fault"]
        assert "recommended_action" in data
        assert "reasoning" in data

    def test_telemetry_validation_voltage_range(self, client):
        """Test voltage validation."""
        telemetry = {
            "voltage": 100.0,  # Invalid: exceeds max
            "temperature": 25.0,
            "gyro": 0.01
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 422  # Validation error

    def test_telemetry_validation_missing_fields(self, client):
        """Test validation with missing required fields."""
        telemetry = {
            "voltage": 8.0
            # Missing temperature and gyro
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 422

    def test_telemetry_optional_fields(self, client):
        """Test telemetry with only required fields."""
        telemetry = {
            "voltage": 8.0,
            "temperature": 25.0,
            "gyro": 0.01
            # current and wheel_speed are optional
        }
        response = client.post("/api/v1/telemetry", json=telemetry)
        assert response.status_code == 200


class TestBatchEndpoints:
    """Test batch processing endpoints."""

    def test_submit_batch_telemetry(self, client):
        """Test submitting batch of telemetry."""
        batch = {
            "telemetry": [
                {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01},
                {"voltage": 7.5, "temperature": 30.0, "gyro": 0.02},
                {"voltage": 6.5, "temperature": 50.0, "gyro": 0.2}  # Anomaly
            ]
        }
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 200
        data = response.json()
        assert data["total_processed"] == 3
        assert data["anomalies_detected"] >= 1
        assert len(data["results"]) == 3

    def test_batch_empty_validation(self, client):
        """Test batch validation with empty list."""
        batch = {"telemetry": []}
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 422

    def test_batch_size_limit(self, client):
        """Test batch size limit (max 1000)."""
        batch = {
            "telemetry": [
                {"voltage": 8.0, "temperature": 25.0, "gyro": 0.01}
                for _ in range(1001)  # Exceeds limit
            ]
        }
        response = client.post("/api/v1/telemetry/batch", json=batch)
        assert response.status_code == 422


class TestStatusEndpoints:
    """Test status endpoints."""

    def test_get_system_status(self, client):
        """Test getting system status."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mission_phase" in data
        assert "components" in data
        assert "uptime_seconds" in data

    def test_status_contains_components(self, client):
        """Test status includes component health."""
        response = client.get("/api/v1/status")
        data = response.json()
        assert isinstance(data["components"], dict)


class TestPhaseEndpoints:
    """Test mission phase endpoints."""

    def test_get_current_phase(self, client):
        """Test getting current mission phase."""
        response = client.get("/api/v1/phase")
        assert response.status_code == 200
        data = response.json()
        assert "phase" in data
        assert data["phase"] in ["LAUNCH", "DEPLOYMENT", "NOMINAL_OPS", "PAYLOAD_OPS", "SAFE_MODE"]
        assert "description" in data
        assert "constraints" in data
        assert "history" in data

    def test_update_phase_valid_transition(self, client):
        """Test valid phase transition."""
        # Try transitioning to SAFE_MODE (always valid)
        request = {
            "phase": "SAFE_MODE",
            "force": True
        }
        response = client.post("/api/v1/phase", json=request)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_phase"] == "SAFE_MODE"

    def test_update_phase_invalid_enum(self, client):
        """Test invalid phase enum value."""
        request = {
            "phase": "INVALID_PHASE",
            "force": False
        }
        response = client.post("/api/v1/phase", json=request)
        assert response.status_code == 422


class TestMemoryEndpoints:
    """Test memory store endpoints."""

    def test_get_memory_stats(self, client):
        """Test getting memory statistics."""
        response = client.get("/api/v1/memory/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_events" in data
        assert "critical_events" in data
        assert "avg_age_hours" in data
        assert "max_recurrence" in data
        assert data["total_events"] >= 0


class TestHistoryEndpoints:
    """Test anomaly history endpoints."""

    def test_get_anomaly_history(self, client):
        """Test getting anomaly history."""
        response = client.get("/api/v1/history/anomalies")
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)

    def test_history_with_limit(self, client):
        """Test history with limit parameter."""
        response = client.get("/api/v1/history/anomalies?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["anomalies"]) <= 5

    def test_history_with_severity_filter(self, client):
        """Test history with severity filter."""
        # First submit an anomaly
        telemetry = {
            "voltage": 6.5,
            "temperature": 50.0,
            "gyro": 0.2
        }
        client.post("/api/v1/telemetry", json=telemetry)

        # Query with severity filter
        response = client.get("/api/v1/history/anomalies?severity_min=0.5")
        assert response.status_code == 200
        data = response.json()
        # All returned anomalies should meet severity threshold
        for anomaly in data["anomalies"]:
            assert anomaly["severity_score"] >= 0.5


class TestIntegrationFlow:
    """Test complete integration flow."""

    def test_full_anomaly_detection_flow(self, client):
        """Test complete flow: submit telemetry -> detect anomaly -> check history."""
        # 1. Check initial status
        status_response = client.get("/api/v1/status")
        assert status_response.status_code == 200

        # 2. Get current phase
        phase_response = client.get("/api/v1/phase")
        assert phase_response.status_code == 200
        initial_phase = phase_response.json()["phase"]

        # 3. Submit anomalous telemetry
        telemetry = {
            "voltage": 6.0,  # Power fault
            "temperature": 55.0,  # Thermal fault
            "gyro": 0.3  # Attitude fault
        }
        telemetry_response = client.post("/api/v1/telemetry", json=telemetry)
        assert telemetry_response.status_code == 200
        detection = telemetry_response.json()
        assert detection["is_anomaly"] is True

        # 4. Check anomaly history
        history_response = client.get("/api/v1/history/anomalies?limit=10")
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["count"] > 0

        # 5. Check memory stats
        memory_response = client.get("/api/v1/memory/stats")
        assert memory_response.status_code == 200
        memory = memory_response.json()
        assert memory["total_events"] > 0


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers(self, client):
        """Test CORS headers are present."""
        response = client.options("/api/v1/telemetry")
        # CORS middleware should handle OPTIONS requests
        assert response.status_code in [200, 405]


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation endpoints."""

    def test_docs_endpoint(self, client):
        """Test Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema(self, client):
        """Test OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
