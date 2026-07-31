import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter by client IP."""

    def __init__(self, rpm: int = 30):
        self.rpm = rpm
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def check(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        # Prune entries older than 60 seconds
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < 60
        ]
        if len(self.requests[client_ip]) >= self.rpm:
            logger.warning("Rate limit exceeded for %s", client_ip)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again shortly.",
            )
        self.requests[client_ip].append(now)
