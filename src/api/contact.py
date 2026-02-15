"""
Contact Form API

Handles contact form submissions with validation, rate limiting, spam protection,
and persistence. Includes admin endpoint for reviewing submissions.
"""

import os
import re
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Any, Union
import asyncio

import aiosqlite
import aiofiles

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator

from src.db.database import get_connection, get_pool_stats, is_pool_enabled


try:
    from backend.redis_client import RedisClient
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


try:
    from core.auth import require_admin
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False


logger = logging.getLogger(__name__)


if AUTH_AVAILABLE:
    async def get_admin_user(user: Any = Depends(require_admin)) -> Any:
        return user
else:
    async def get_admin_user(user: Any = None) -> Any:
        return None


router = APIRouter(prefix="/api/contact", tags=["contact"])


DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "contact_submissions.db"
NOTIFICATION_LOG = DATA_DIR / "contact_notifications.log"
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "support@astraguard.ai")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", None)


_raw_trusted = os.getenv("TRUSTED_PROXIES", "")
TRUSTED_PROXIES: set[str] = {ip.strip() for ip in _raw_trusted.split(",") if ip.strip()}


RATE_LIMIT_SUBMISSIONS = 5
RATE_LIMIT_WINDOW = 3600


class ContactSubmission(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., min_length=5, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=10, max_length=5000)
    website: Optional[str] = Field(None)

    @field_validator("name", "subject", "message", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        if v:
            v = re.sub(r'[<>"\'&]', "", v)
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower() if v else v


class ContactResponse(BaseModel):
    success: bool
    message: str
    submission_id: Optional[int] = None


class SubmissionRecord(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    subject: str
    message: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    submitted_at: str
    status: str


class SubmissionsResponse(BaseModel):
    total: int
    limit: int
    offset: int
    submissions: List[SubmissionRecord]


def init_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_submitted_at
        ON contact_submissions(submitted_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_status
        ON contact_submissions(status)
    """)

    conn.commit()
    conn.close()


class InMemoryRateLimiter:

    def __init__(self) -> None:
        self.requests: dict[str, list[datetime]] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=window)

            if key in self.requests:
                self.requests[key] = [ts for ts in self.requests[key] if ts > cutoff]
            else:
                self.requests[key] = []

            if len(self.requests[key]) >= limit:
                return False

            self.requests[key].append(now)

            if not self.requests[key]:
                del self.requests[key]

            return True


_in_memory_limiter = InMemoryRateLimiter()


async def check_rate_limit(ip_address: str) -> bool:
    return await _in_memory_limiter.is_allowed(
        f"contact:{ip_address}",
        RATE_LIMIT_SUBMISSIONS,
        RATE_LIMIT_WINDOW,
    )


def get_client_ip(request: Request) -> str:
    direct_ip: str = "unknown"
    if request.client:
        direct_ip = request.client.host

    if direct_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

    return direct_ip


async def save_submission(
    submission: ContactSubmission,
    ip_address: str,
    user_agent: str,
) -> Optional[int]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO contact_submissions
                (name, email, phone, subject, message, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission.name,
                submission.email,
                submission.phone,
                submission.subject,
                submission.message,
                ip_address,
                user_agent,
            ),
        )
        await conn.commit()
        return cursor.lastrowid


async def log_notification(
    submission: ContactSubmission,
    submission_id: Optional[int],
) -> None:
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "submission_id": submission_id,
        "name": submission.name,
        "email": submission.email,
        "subject": submission.subject,
        "message": (
            submission.message[:100] + "..."
            if len(submission.message) > 100
            else submission.message
        ),
    }

    async with aiofiles.open(NOTIFICATION_LOG, "a") as f:
        await f.write(json.dumps(log_entry) + "\n")


async def send_email_notification(
    submission: ContactSubmission,
    submission_id: Optional[int],
) -> None:
    if SENDGRID_API_KEY:
        try:
            pass
        except Exception as e:
            logger.warning(
                "SendGrid send failed, falling back to file log",
                exc_info=e,
            )
            await log_notification(submission, submission_id)
    else:
        await log_notification(submission, submission_id)



@router.post("", response_model=ContactResponse, status_code=201)
async def submit_contact_form(
    submission: ContactSubmission,
    request: Request,
) -> Union[JSONResponse, ContactResponse]:


    if submission.website:
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Thank you for your message! We'll get back to you within 24-48 hours.",
            },
        )

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")

    if not await check_rate_limit(ip_address):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions. Please try again later.",
        )

    try:
        submission_id = await save_submission(submission, ip_address, user_agent)
    except aiosqlite.Error as e:
        logger.error(
            "Database save failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "ip_address": ip_address,
                "email": submission.email,
                "subject": submission.subject,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save submission. Please try again later.",
        )
    except Exception as e:
        logger.error(
            "Unexpected database error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "ip_address": ip_address,
                "email": submission.email,
            },
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later.",
        )

    try:
        await send_email_notification(submission, submission_id)
    except Exception as e:
        logger.warning(
            "Notification failed but submission was saved",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "submission_id": submission_id,
                "email": submission.email,
                "subject": submission.subject,
            },
        )

    return ContactResponse(
        success=True,
        message="Thank you for your message! We'll get back to you within 24-48 hours.",
        submission_id=submission_id,
    )


@router.get("/submissions", response_model=SubmissionsResponse)
async def get_submissions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, pattern="^(pending|resolved|spam)$"),
    current_user: Any = Depends(get_admin_user),
) -> SubmissionsResponse:

    where_clause = ""
    params: list[Any] = []

    if status_filter:
        where_clause = "WHERE status = ?"
        params.append(status_filter)

    count_query = f"SELECT COUNT(*) AS total FROM contact_submissions {where_clause}"
    select_query = f"""
        SELECT id, name, email, phone, subject, message,
               ip_address, user_agent, submitted_at, status
        FROM contact_submissions
        {where_clause}
        ORDER BY submitted_at DESC
        LIMIT ? OFFSET ?
    """

    async with get_connection() as conn:
        conn.row_factory = aiosqlite.Row

        async with conn.execute(count_query, params) as cursor:
            row = await cursor.fetchone()
            total: int = row["total"]

        async with conn.execute(select_query, [*params, limit, offset]) as cursor:
            rows = await cursor.fetchall()

    submissions = [
        SubmissionRecord(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            phone=row["phone"],
            subject=row["subject"],
            message=row["message"],
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            submitted_at=row["submitted_at"],
            status=row["status"],
        )
        for row in rows
    ]

    return SubmissionsResponse(
        total=total,
        limit=limit,
        offset=offset,
        submissions=submissions,
    )


@router.patch("/submissions/{submission_id}/status")
async def update_submission_status(
    submission_id: int,
    status: str = Query(..., pattern="^(pending|resolved|spam)$"),
    current_user: Any = Depends(get_admin_user),
) -> dict[str, Any]:

    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE contact_submissions SET status = ? WHERE id = ?",
            (status, submission_id),
        )
        await conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Submission not found")

    return {"success": True, "message": f"Status updated to {status}"}


@router.get("/health")
async def contact_health() -> dict[str, Any]:

    try:
        async with get_connection() as conn:
            async with conn.execute(
                "SELECT COUNT(*) FROM contact_submissions"
            ) as cursor:
                row = await cursor.fetchone()
                total_submissions: int = row[0]

        rate_limiter_status = "redis" if REDIS_AVAILABLE else "in-memory"

        return {
            "status": "healthy",
            "database": "connected",
            "total_submissions": total_submissions,
            "rate_limiter": rate_limiter_status,
            "email_configured": SENDGRID_API_KEY is not None,
        }

    except aiosqlite.Error as e:
        logger.error(
            "Database health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "db_path": str(DB_PATH),
            },
        )
        raise HTTPException(status_code=503, detail="Database connection failed")

    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise HTTPException(status_code=503, detail="Service health check failed")


@router.get("/pool-health")
async def pool_health() -> dict[str, Any]:
    """
    Get connection pool health statistics.
    
    Returns pool metrics including active connections, idle connections,
    total created, timeouts, and average wait time.
    """
    if not is_pool_enabled():
        return {
            "status": "disabled",
            "message": "Connection pooling is not enabled"
        }
    
    stats = await get_pool_stats()
    
    if stats is None:
        raise HTTPException(
            status_code=503,
            detail="Pool statistics unavailable"
        )
    
    return {
        "status": "healthy",
        "pool": {
            "active_connections": stats.active_connections,
            "idle_connections": stats.idle_connections,
            "total_connections": stats.total_connections,
            "max_size": stats.max_size,
            "total_created": stats.total_created,
            "total_acquisitions": stats.total_acquisitions,
            "total_releases": stats.total_releases,
            "total_timeouts": stats.total_timeouts,
            "total_errors": stats.total_errors,
            "average_wait_time_ms": round(stats.average_wait_time * 1000, 2),
        }
    }
