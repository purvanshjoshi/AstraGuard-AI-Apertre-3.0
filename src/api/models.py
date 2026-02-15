"""
Pydantic models for API request/response validation.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

logger = logging.getLogger(__name__)


class ModelValidationError(Exception):
    """Raised when model validation fails with actionable context."""

    def __init__(self, message: str, field_name: Optional[str] = None,
                 provided_value: Optional[Any] = None,
                 constraints: Optional[Dict[str, Any]] = None):
        self.message = message
        self.field_name = field_name
        self.provided_value = provided_value
        self.constraints = constraints or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "field_name": self.field_name,
            "provided_value": self.provided_value,
            "constraints": self.constraints,
        }


class UserRole(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"        # Full system access including user management
    OPERATOR = "operator"  # Full operational access (telemetry, phase changes)
    ANALYST = "analyst"    # Read-only access (status, history, monitoring)


class MissionPhaseEnum(str, Enum):
    """Mission phase enumeration."""
    LAUNCH = "LAUNCH"
    DEPLOYMENT = "DEPLOYMENT"
    NOMINAL_OPS = "NOMINAL_OPS"
    PAYLOAD_OPS = "PAYLOAD_OPS"
    SAFE_MODE = "SAFE_MODE"


class TelemetryInput(BaseModel):
    """Single telemetry data point."""
    voltage: float = Field(..., ge=0, le=50, description="Voltage in volts")
    temperature: float = Field(..., ge=-100, le=150, description="Temperature in Celsius")
    gyro: float = Field(..., description="Gyroscope reading in rad/s")
    current: Optional[float] = Field(None, ge=0, description="Current in amperes")
    wheel_speed: Optional[float] = Field(None, ge=0, description="Reaction wheel speed in RPM")

    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage: Optional[float] = Field(None, ge=0, le=100, description="Memory usage percentage")
    network_latency: Optional[float] = Field(None, ge=0, description="Network latency in ms")
    disk_io: Optional[float] = Field(None, ge=0, description="Disk I/O operations per second")
    error_rate: Optional[float] = Field(None, ge=0, description="Error rate per minute")
    response_time: Optional[float] = Field(None, ge=0, description="Response time in ms")
    active_connections: Optional[int] = Field(None, ge=0, description="Number of active connections")

    timestamp: Optional[datetime] = Field(None, description="Telemetry timestamp")

    @field_validator('timestamp', mode='before')
    @classmethod
    def set_timestamp(cls, v) -> datetime:
        """Set timestamp to now if not provided; parse ISO strings; warn on bad input."""
        if v is None:
            return datetime.now()

        if isinstance(v, datetime):
            return v

        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError as exc:
                logger.warning(
                    "timestamp_parsing_failed",
                    extra={
                        "provided_value": v[:50] if len(v) > 50 else v,
                        "error": str(exc),
                        "action": "using_current_timestamp",
                    },
                )
                return datetime.now()

        # Any other type: log and fall back — do NOT silently discard without trace.
        logger.warning(
            "timestamp_type_invalid",
            extra={
                "provided_value": type(v).__name__,
                "expected_types": ["None", "datetime", "str"],
                "action": "using_current_timestamp",
            },
        )
        return datetime.now()


class TelemetryBatch(BaseModel):
    """Batch of telemetry data points.

    Pydantic enforces 1 ≤ len ≤ 1000 via Field constraints before the
    validator runs, so the validator focuses only on runtime logging.
    """
    telemetry: List[TelemetryInput] = Field(..., min_length=1, max_length=1000)

    @field_validator('telemetry')
    @classmethod
    def validate_telemetry_batch(cls, v: List[TelemetryInput]) -> List[TelemetryInput]:
        """Log accepted batch size; Field constraints already enforce bounds."""
        logger.debug(
            "telemetry_batch_accepted",
            extra={"batch_size": len(v)},
        )
        return v


class AnomalyResponse(BaseModel):
    """Response from anomaly detection."""
    is_anomaly: bool
    anomaly_score: float = Field(..., ge=0, le=1)
    anomaly_type: str
    severity_score: float = Field(..., ge=0, le=1)
    severity_level: str
    mission_phase: str
    recommended_action: str
    escalation_level: str
    is_allowed: bool
    allowed_actions: List[str]
    should_escalate_to_safe_mode: bool
    confidence: float = Field(..., ge=0, le=1)
    reasoning: str
    recurrence_count: int = Field(..., ge=0)
    timestamp: datetime


class BatchAnomalyResponse(BaseModel):
    """Response from batch anomaly detection."""
    total_processed: int
    anomalies_detected: int
    results: List[AnomalyResponse]


class SystemStatus(BaseModel):
    """System health and status."""
    status: str = Field(..., description="Overall system status")
    mission_phase: str
    components: Dict[str, Any]
    uptime_seconds: float
    timestamp: datetime


class PhaseUpdateRequest(BaseModel):
    """Request to update mission phase."""
    phase: MissionPhaseEnum
    force: bool = Field(False, description="Force transition even if invalid")

    @field_validator('phase', mode='before')
    @classmethod
    def validate_phase(cls, v) -> MissionPhaseEnum:
        """Normalise and validate mission phase input.

        Raises
        ------
        ValueError
            When the string value is not a recognised MissionPhaseEnum member.
        TypeError
            When the value is neither a string nor a MissionPhaseEnum instance.
            Pydantic re-wraps this in a ValidationError so callers always get
            a consistent ValidationError at the API boundary.
        """
        if isinstance(v, MissionPhaseEnum):
            return v

        if isinstance(v, str):
            try:
                phase = MissionPhaseEnum(v.upper())
                logger.info(
                    "phase_normalized",
                    extra={
                        "original": v,
                        "normalized": phase.value,
                        "action": "normalized_to_enum",
                    },
                )
                return phase
            except ValueError:
                valid_phases = [p.value for p in MissionPhaseEnum]
                logger.error(
                    "invalid_phase_value",
                    extra={
                        "provided": v,
                        "valid_values": valid_phases,
                    },
                )
                raise ValueError(
                    f"Invalid phase: {v!r}. Valid phases: {valid_phases}"
                )

        # Non-string, non-enum input: raise TypeError so the test can catch it
        # directly, and Pydantic wraps it in ValidationError for API consumers.
        raise TypeError(
            f"Phase must be a string or MissionPhaseEnum, got {type(v).__name__!r}"
        )


class PhaseUpdateResponse(BaseModel):
    """Response from phase update."""
    success: bool
    previous_phase: str
    new_phase: str
    message: str
    timestamp: datetime


class MemoryStats(BaseModel):
    """Memory store statistics."""
    total_events: int
    critical_events: int
    avg_age_hours: float
    max_recurrence: int
    timestamp: datetime


class AnomalyHistoryQuery(BaseModel):
    """Query parameters for anomaly history.

    Field-level constraints (ge/le) are the authoritative source of truth for
    limit and severity_min boundaries; they fire before validators.  The
    validators handle logging and the datetime edge-cases.
    """
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    severity_min: Optional[float] = Field(None, ge=0, le=1)

    @field_validator('limit')
    @classmethod
    def log_limit(cls, v: int) -> int:
        """Log the accepted limit value (bounds already enforced by Field)."""
        logger.debug("limit_accepted", extra={"limit": v})
        return v

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_datetime(cls, v) -> Optional[datetime]:
        """Parse ISO datetime strings; return None and warn on parse failure."""
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(
                    "datetime_parse_failed",
                    extra={
                        "provided_value": v[:50] if len(v) > 50 else v,
                        "action": "ignored",
                    },
                )
                return None
        return v

    @field_validator('severity_min')
    @classmethod
    def log_severity_min(cls, v: Optional[float]) -> Optional[float]:
        """Log the accepted severity_min (bounds already enforced by Field)."""
        if v is not None:
            logger.debug("severity_min_accepted", extra={"severity_min": v})
        return v

    @field_validator('end_time')
    @classmethod
    def validate_time_range(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Ensure end_time is not earlier than start_time."""
        start_time = info.data.get('start_time')
        if start_time is not None and v is not None and v < start_time:
            logger.warning(
                "time_range_invalid",
                extra={
                    "start_time": start_time.isoformat(),
                    "end_time": v.isoformat(),
                    "action": "end_time_set_to_start_time",
                },
            )
            return start_time
        return v


class AnomalyHistoryResponse(BaseModel):
    """Response with anomaly history."""
    count: int
    anomalies: List[AnomalyResponse]
    start_time: Optional[datetime]
    end_time: Optional[datetime]


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    uptime_seconds: Optional[float] = None
    mission_phase: Optional[str] = None
    components_status: Optional[Dict[str, Dict[str, Any]]] = None
    error: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Strip, lower-case, and validate username length and non-emptiness."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")

        username = v.strip().lower()

        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")

        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")

        return username


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str


class UserCreateRequest(BaseModel):
    """Request to create a new user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    role: UserRole
    password: Optional[str] = Field(None, min_length=8)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username for security and formatting."""
        if not v or not v.strip():
            raise ValueError("Username cannot be empty or whitespace only")

        username = v.strip()

        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")

        if len(username) > 50:
            raise ValueError("Username cannot exceed 50 characters")

        if not username[0].isalnum():
            logger.warning(
                "username_starts_with_special",
                extra={
                    "username": username[:10] + "***" if len(username) > 10 else username,
                    "warning": "Username starts with special character",
                },
            )

        return username.lower()

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        """Log a nudge when password is at the minimum length; Field enforces the floor."""
        if v is None:
            return v

        if len(v) < 8:
            # Field(min_length=8) will already reject this; the log is informational.
            logger.warning(
                "password_too_short",
                extra={
                    "min_length": 8,
                    "provided_length": len(v),
                    "warning": "Password meets minimum length but consider longer passwords",
                },
            )

        return v


class UserResponse(BaseModel):
    """User information response."""
    id: str
    username: str
    email: str
    role: str
    created_at: datetime
    is_active: bool


class APIKeyCreateRequest(BaseModel):
    """Request to create an API key."""
    name: str = Field(..., min_length=1, max_length=100)
    permissions: List[str] = Field(..., min_length=1)

    @field_validator('name')
    @classmethod
    def validate_api_key_name(cls, v: str) -> str:
        """Validate and trim API key name."""
        if not v or not v.strip():
            raise ValueError("API key name cannot be empty")

        name = v.strip()

        if len(name) > 100:
            raise ValueError("API key name cannot exceed 100 characters")

        logger.info(
            "api_key_name_valid",
            extra={
                "name_length": len(name),
                "action": "accepted",
            },
        )
        return name

    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        """Normalise to lowercase and warn about unrecognised permissions."""
        if not v:
            raise ValueError("At least one permission must be specified")

        valid_permissions: frozenset[str] = frozenset({'read', 'write', 'admin', 'execute'})
        normalised = [p.lower() for p in v]
        invalid_permissions = set(normalised) - valid_permissions

        if invalid_permissions:
            logger.warning(
                "invalid_permissions_provided",
                extra={
                    "invalid_permissions": sorted(invalid_permissions),
                    "valid_permissions": sorted(valid_permissions),
                    "action": "accepted_with_warning",
                },
            )

        return normalised


class APIKeyResponse(BaseModel):
    """API key information response (without the key value)."""
    id: str
    name: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]


class APIKeyCreateResponse(BaseModel):
    """API key creation response (includes the key value)."""
    id: str
    name: str
    key: str
    permissions: List[str]
    created_at: datetime
    expires_at: Optional[datetime]