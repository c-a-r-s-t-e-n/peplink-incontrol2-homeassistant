"""Small read-only InControl 2 OAuth API client."""
from datetime import datetime, timedelta, timezone
import logging
from aiohttp import ClientResponseError, ClientError
from .const import API_BASE, TOKEN_URL

_LOGGER = logging.getLogger(__name__)

class IC2Error(Exception):
    """InControl 2 request failed."""

class IC2Client:
    def __init__(self, session, client_id, client_secret):
        self._session = session
        self._id = client_id
        self._secret = client_secret
        self._token = None
        self._expiry = datetime.min.replace(tzinfo=timezone.utc)

    async def _authorize(self):
        form = {"grant_type": "client_credentials", "client_id": self._id, "client_secret": self._secret}
        try:
            async with self._session.post(TOKEN_URL, data=form, timeout=20) as r:
                r.raise_for_status()
                doc = await r.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as exc:
            raise IC2Error("OAuth authentication failed") from exc
        token = doc.get("access_token")
        if not token:
            raise IC2Error("OAuth token not returned")
        self._token = token
        self._expiry = datetime.now(timezone.utc) + timedelta(seconds=max(60, int(doc.get("expires_in", 3600)) - 90))

    async def get(self, path, params=None):
        if not self._token or datetime.now(timezone.utc) >= self._expiry:
            await self._authorize()
        for attempt in range(2):
            try:
                async with self._session.get(API_BASE + path, params=params,
                                             headers={"Authorization": f"Bearer {self._token}"}, timeout=25) as response:
                    if response.status == 401 and attempt == 0:
                        await self._authorize()
                        continue
                    response.raise_for_status()
                    data = await response.json(content_type=None)
            except (ClientError, TimeoutError, ValueError) as exc:
                raise IC2Error(f"API request failed for {path.rsplit('/', 1)[-1]}") from exc
            code = data.get("resp_code")
            if code not in (None, "SUCCESS", "PENDING"):
                raise IC2Error(f"InControl 2 returned {code}")
            if code == "PENDING":
                return None
            return data.get("data")
        raise IC2Error("OAuth session expired")
