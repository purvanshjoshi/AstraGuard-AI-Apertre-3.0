import pytest
import asyncio
import pickle
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock, mock_open
from typing import Dict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from anomaly import anomaly_detector
from core.error_handling import ModelLoadError, AnomalyEngineError
from core.input_validation import ValidationError
from core.timeout_handler import TimeoutError as CustomTimeoutError
from core.circuit_breaker import CircuitOpenError


class SimpleModel:
    def predict(self, X):
        return [False]
    
    def score_samples(self, X):
        return [0.3]


@pytest.fixture
def sample_telemetry_data():
    return {
        "voltage": 8.0,
        "temperature": 25.0,
        "gyro": 0.05,
        "current": 1.0,
        "wheel_speed": 5.0,
    }


@pytest.fixture
def anomalous_telemetry_data():
    return {
        "voltage": 6.5,
        "temperature": 45.0,
        "gyro": 0.15,
        "current": 1.0,
        "wheel_speed": 5.0,
    }


@pytest.fixture
def invalid_telemetry_data():
    return {
        "voltage": "invalid",
        "temperature": None,
        "gyro": "not_a_number",
    }


@pytest.fixture(autouse=True)
def reset_module_state():
    anomaly_detector._MODEL = None
    anomaly_detector._MODEL_LOADED = False
    anomaly_detector._USING_HEURISTIC_MODE = False
    yield
    anomaly_detector._MODEL = None
    anomaly_detector._MODEL_LOADED = False
    anomaly_detector._USING_HEURISTIC_MODE = False


@pytest.fixture
def mock_model():
    model = Mock()
    model.predict = Mock(return_value=[False])
    model.score_samples = Mock(return_value=[0.3])
    return model


@pytest.fixture
def mock_health_monitor():
    monitor = Mock()
    monitor.register_component = Mock()
    monitor.mark_healthy = Mock()
    monitor.mark_degraded = Mock()
    return monitor


@pytest.fixture
def mock_resource_monitor():
    monitor = Mock()
    monitor.check_resource_health = Mock(return_value={'overall': 'healthy'})
    return monitor


class TestHeuristicDetection:

    def test_heuristic_normal_data(self, sample_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            sample_telemetry_data
        )
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert not is_anomalous or score < 0.7

    def test_heuristic_anomalous_voltage(self):
        data = {"voltage": 6.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.4

    def test_heuristic_anomalous_temperature(self):
        data = {"voltage": 8.0, "temperature": 50.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_anomalous_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.2}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_multiple_anomalies(self, anomalous_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            anomalous_telemetry_data
        )
        assert is_anomalous
        assert score > 0.8

    def test_heuristic_missing_fields(self):
        data = {}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_heuristic_invalid_data_types(self, invalid_telemetry_data):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(
            invalid_telemetry_data
        )
        assert isinstance(is_anomalous, bool)
        assert score >= 0.5

    def test_heuristic_non_dict_input(self):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic("not a dict")
        assert not is_anomalous
        assert score == 0.0

    def test_heuristic_score_capped_at_one(self):
        data = {"voltage": 5.0, "temperature": 60.0, "gyro": 0.5}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score <= 1.0


class TestModelLoading:

    @pytest.mark.asyncio
    async def test_load_model_success(self, mock_health_monitor):
        simple_model = SimpleModel()
        pickled_data = pickle.dumps(simple_model)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=pickled_data)), \
             patch('asyncio.to_thread', return_value=simple_model), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            result = await anomaly_detector._load_model_impl()
            
            assert result is True
            assert anomaly_detector._MODEL_LOADED is True
            assert anomaly_detector._USING_HEURISTIC_MODE is False
            mock_health_monitor.mark_healthy.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_file_not_found(self, mock_health_monitor):
        with patch('os.path.exists', return_value=False), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(ModelLoadError) as exc_info:
                await anomaly_detector._load_model_impl()
            
            assert "Model file not found" in str(exc_info.value)
            assert anomaly_detector._MODEL_LOADED is False

    @pytest.mark.asyncio
    async def test_load_model_numpy_import_error(self, mock_health_monitor):
        with patch('builtins.__import__', side_effect=ImportError("No module named 'numpy'")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            result = await anomaly_detector._load_model_impl()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True
            assert anomaly_detector._MODEL_LOADED is False
            mock_health_monitor.mark_degraded.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_pickle_error(self, mock_health_monitor):
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('asyncio.to_thread', side_effect=pickle.UnpicklingError("Bad pickle")), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor):
            
            with pytest.raises(pickle.UnpicklingError):
                await anomaly_detector._load_model_impl()

    @pytest.mark.asyncio
    async def test_load_model_fallback(self):
        result = await anomaly_detector._load_model_fallback()
        
        assert result is False
        assert anomaly_detector._USING_HEURISTIC_MODE is True

    @pytest.mark.asyncio
    async def test_load_model_circuit_breaker_open(self):
        mock_cb = Mock()
        mock_cb.call = AsyncMock(side_effect=CircuitOpenError("Circuit open"))
        
        with patch.object(anomaly_detector, '_model_loader_cb', mock_cb):
            result = await anomaly_detector.load_model()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True

    @pytest.mark.asyncio
    async def test_load_model_unexpected_error(self):
        mock_cb = Mock()
        mock_cb.call = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        
        with patch.object(anomaly_detector, '_model_loader_cb', mock_cb):
            result = await anomaly_detector.load_model()
            
            assert result is False
            assert anomaly_detector._USING_HEURISTIC_MODE is True


class TestDetectAnomaly:

    @pytest.mark.asyncio
    async def test_detect_anomaly_with_model(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [0.3]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
            assert not is_anomalous
            mock_health_monitor.mark_healthy.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_heuristic_mode(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = None
        anomaly_detector._MODEL_LOADED = False
        anomaly_detector._USING_HEURISTIC_MODE = True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_critical_resources(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        mock_resource_monitor.check_resource_health.return_value = {'overall': 'critical'}
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            mock_health_monitor.mark_degraded.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_validation_error(
        self, mock_health_monitor, mock_resource_monitor
    ):
        invalid_data = {"invalid": "data"}
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', side_effect=ValidationError("Invalid data")), \
             patch('anomaly.anomaly_detector.load_model', return_value=False):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(invalid_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_prediction_error(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=RuntimeError("Model error")):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert anomaly_detector._USING_HEURISTIC_MODE is True
            mock_health_monitor.mark_degraded.assert_called()

    @pytest.mark.asyncio
    async def test_detect_anomaly_model_without_score_samples(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        mock_model = Mock()
        mock_model.predict = Mock(return_value=[True])
        
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[[True], [0.5]]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_detect_anomaly_score_normalization(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [1.5]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_detect_anomaly_none_score(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = mock_model
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('asyncio.to_thread', side_effect=[
                 [False],
                 [None]
             ]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert score == 0.5

    @pytest.mark.asyncio
    async def test_detect_anomaly_loads_model_if_needed(
        self, sample_telemetry_data, mock_model, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL_LOADED = False
        
        async def mock_load_model():
            anomaly_detector._MODEL = mock_model
            anomaly_detector._MODEL_LOADED = True
            return True
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data), \
             patch('anomaly.anomaly_detector.load_model', side_effect=mock_load_model), \
             patch('asyncio.to_thread', side_effect=[[False], [0.3]]):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)


class TestIntegration:

    @pytest.mark.asyncio
    async def test_end_to_end_normal_flow(
        self, sample_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        simple_model = SimpleModel()
        pickled_data = pickle.dumps(simple_model)
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=pickled_data)), \
             patch('asyncio.to_thread', side_effect=[
                 simple_model,
                 [False],
                 [0.3]
             ]), \
             patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=sample_telemetry_data):
            
            load_result = await anomaly_detector.load_model()
            assert load_result is True
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(sample_telemetry_data)
            
            assert not is_anomalous
            assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_graceful_degradation(
        self, anomalous_telemetry_data, mock_health_monitor, mock_resource_monitor
    ):
        anomaly_detector._MODEL = Mock()
        anomaly_detector._MODEL_LOADED = True
        anomaly_detector._USING_HEURISTIC_MODE = False
        
        with patch('anomaly.anomaly_detector.get_health_monitor', return_value=mock_health_monitor), \
             patch('anomaly.anomaly_detector.get_resource_monitor', return_value=mock_resource_monitor), \
             patch('anomaly.anomaly_detector.TelemetryData.validate', return_value=anomalous_telemetry_data), \
             patch('asyncio.to_thread', side_effect=RuntimeError("Model failed")):
            
            is_anomalous, score = await anomaly_detector.detect_anomaly(anomalous_telemetry_data)
            
            assert isinstance(is_anomalous, bool)
            assert isinstance(score, float)
            assert anomaly_detector._USING_HEURISTIC_MODE is True


class TestEdgeCases:

    def test_heuristic_exact_threshold_voltage_low(self):
        data = {"voltage": 7.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_voltage_high(self):
        data = {"voltage": 9.0, "temperature": 25.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_temperature(self):
        data = {"voltage": 8.0, "temperature": 40.0, "gyro": 0.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_exact_threshold_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": 0.1}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_negative_gyro(self):
        data = {"voltage": 8.0, "temperature": 25.0, "gyro": -0.15}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert score >= 0.3

    def test_heuristic_empty_dict(self):
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic({})
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)

    def test_heuristic_partial_data(self):
        data = {"voltage": 8.0}
        is_anomalous, score = anomaly_detector._detect_anomaly_heuristic(data)
        assert isinstance(is_anomalous, bool)
        assert isinstance(score, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=anomaly.anomaly_detector", "--cov-report=html", "--cov-report=term"])
