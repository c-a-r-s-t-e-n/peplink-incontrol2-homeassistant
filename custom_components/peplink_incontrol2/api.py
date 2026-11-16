"""Read-only OAuth client with bounded responses, pacing and safe errors."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from time import monotonic

from aiohttp import ClientError

from .const import API_BASE, TOKEN_URL

MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class IC2Error(Exception):
    """A cloud request failed without exposing response bodies or credentials."""


class IC2AuthError(IC2Error):
    """Credentials are rejected and need to be replaced."""


class IC2RateLimitError(IC2Error):
    """The cloud requested a cooldown."""


def retry_delay(value):
    """Accept Retry-After seconds or HTTP dates; never retry before the deadline."""
    try:
        return max(1.0, float(value))
    except (TypeError, ValueError):
        try:
            return max(1.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 60.0


class IC2Client:
    def __init__(self, session, client_id, client_secret):
        self._session = session
        self._id = client_id
        self._secret = client_secret
        self._token = None
        self._expiry = datetime.min.replace(tzinfo=timezone.utc)
        self._lock = asyncio.Lock()
        self._next_request = 0.0
        self._cooldown = 0.0

    async def _json(self, response):
        body = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise IC2Error("Cloud response exceeds size limit")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise IC2Error("Unexpected cloud response structure")
        return data

    async def _authorize(self):
        form = {"grant_type": "client_credentials", "client_id": self._id, "client_secret": self._secret}
        try:
            async with self._session.post(TOKEN_URL, data=form, timeout=20, allow_redirects=False) as response:
                if response.status in (400, 401, 403):
                    raise IC2AuthError("OAuth credentials rejected")
                self._check_status(response)
                doc = await self._json(response)
            token = doc.get("access_token")
            if not isinstance(token, str) or not token:
                raise IC2Error("OAuth token not returned")
            lifetime = max(1, int(doc.get("expires_in", 3600)))
        except (ClientError, TimeoutError, ValueError, TypeError) as exc:
            raise IC2Error("OAuth authentication failed") from exc
        self._token = token
        self._expiry = datetime.now(timezone.utc) + timedelta(seconds=max(1, lifetime - min(90, lifetime / 10)))

    def _check_status(self, response):
        if response.status == 429:
            self._cooldown = monotonic() + retry_delay(response.headers.get("Retry-After"))
            raise IC2RateLimitError("Cloud rate limit; waiting for next scheduled refresh")
        if response.status >= 300:
            raise IC2Error(f"Cloud HTTP error {response.status}")

    async def get(self, path, params=None):
        async with self._lock:
            if monotonic() < self._cooldown:
                raise IC2RateLimitError("Cloud cooldown active")
            if not self._token or datetime.now(timezone.utc) >= self._expiry:
                await self._authorize()
            for attempt in range(2):
                await asyncio.sleep(max(0, self._next_request - monotonic()))
                self._next_request = monotonic() + 0.1
                try:
                    async with self._session.get(
                        API_BASE + path,
                        params=params,
                        headers={"Authorization": f"Bearer {self._token}"},
                        timeout=25,
                        allow_redirects=False,
                    ) as response:
                        if response.status == 401:
                            if attempt == 0:
                                await self._authorize()
                                continue
                            raise IC2AuthError("OAuth session rejected")
                        self._check_status(response)
                        data = await self._json(response)
                except (ClientError, TimeoutError, ValueError) as exc:
                    raise IC2Error("Cloud transport or JSON error") from exc
                code = data.get("resp_code")
                if code == "PENDING":
                    return None
                if code not in (None, "SUCCESS"):
                    raise IC2Error("Cloud report rejected")
                return data.get("data")
        raise IC2AuthError("OAuth session expired")
