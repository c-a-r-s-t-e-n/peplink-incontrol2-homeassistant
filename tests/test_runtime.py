"""Regression tests using real Home Assistant entity and coordinator classes."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.peplink_incontrol2.api import IC2AuthError, IC2Client, IC2Error, IC2RateLimitError
from custom_components.peplink_incontrol2.binary_sensor import PeplinkOnline
from custom_components.peplink_incontrol2.const import DOMAIN
from custom_components.peplink_incontrol2.coordinator import PeplinkCoordinator
from custom_components.peplink_incontrol2.diagnostics import async_get_config_entry_diagnostics
from custom_components.peplink_incontrol2.quality import latest_survey, retain_samples
from custom_components.peplink_incontrol2.sensor import PeplinkSensor, PeplinkWanQuality, async_setup_entry


@pytest.fixture
async def coordinator(tmp_path):
    entry = SimpleNamespace(entry_id="test", async_on_unload=lambda fn: None)
    return PeplinkCoordinator(HomeAssistant(str(tmp_path)), SimpleNamespace(get=AsyncMock()), entry)


async def inventory(path, params=None):
    if path == "/rest/o":
        return [{"id": "org"}]
    if path.endswith("/g"):
        return [{"id": 1}]
    if path.endswith("/d"):
        return [{"id": 2, "status": "online", "interfaces": [{"id": 1}]}]
    if path.endswith("/d/2"):
        return {}
    if path.endswith("/loc"):
        return {}
    if path.endswith("/wan_quality"):
        return {"stat": [{"ts": 10, "lms": 15}]} if params.get("wan_id") else {"wans": [{"id": 1}]}
    return []


async def test_setup_defers_reports_and_elapsed_polling(coordinator):
    c = coordinator
    c.client.get.side_effect = inventory
    data = await c._async_update_data()
    assert len(data) == 1
    assert len(c.client.get.call_args_list) == 5
    c.client.get.reset_mock()
    data = await c._async_update_data()
    assert data["org_1_2"]["detail"]["report_status"] == "complete"
    assert data["org_1_2"]["detail"]["wan_quality_by_wan"]["1"]["stat"][0]["lms"] == 15
    assert len(c.client.get.call_args_list) > 5
    c.client.get.reset_mock()
    await c._async_update_data()
    assert len(c.client.get.call_args_list) == 5


@pytest.mark.parametrize("error", [IC2AuthError, IC2RateLimitError])
async def test_optional_does_not_swallow_global_errors(coordinator, error):
    coordinator.client.get.side_effect = error("safe")
    with pytest.raises(error):
        await coordinator._optional("/rest/test")


async def test_auth_requests_reauthentication(coordinator):
    coordinator.client.get.side_effect = IC2AuthError("safe")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_pending_inventory_does_not_remove_devices(coordinator):
    coordinator.client.get.return_value = None
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_optional_failure_is_partial(coordinator):
    async def response(path, params=None):
        if path.endswith("/availability"):
            raise IC2Error("safe")
        return await inventory(path, params)

    coordinator.client.get.side_effect = response
    await coordinator._async_update_data()
    data = await coordinator._async_update_data()
    assert data["org_1_2"]["detail"]["report_status"] == "partial"


async def test_cache_pruned_after_confirmed_empty_inventory(coordinator):
    coordinator._detail_cache["removed"] = {"location": {}}
    coordinator._report_due["removed"] = 1
    coordinator.client.get.return_value = []
    assert await coordinator._async_update_data() == {}
    assert not coordinator._detail_cache and not coordinator._report_due


@pytest.mark.parametrize("value,expected", [("online", True), ("offline", False), ("unknown", None), (None, None)])
async def test_unknown_connectivity_not_offline(coordinator, value, expected):
    coordinator.data = {"k": {"device": {"status": value}}}
    entity = PeplinkOnline(coordinator, "k")
    assert entity.is_on is expected
    coordinator.data = {}
    assert not entity.available


async def test_dynamic_entities_and_no_duplicates(coordinator):
    c = coordinator
    c.data = {"k": {"device": {"interfaces": []}, "detail": {}}}
    c.hass.data[DOMAIN] = {"test": c}
    added = []
    c.async_add_listener = lambda callback: setattr(c, "discover", callback) or (lambda: None)
    await async_setup_entry(c.hass, SimpleNamespace(entry_id="test", async_on_unload=lambda fn: None), added.extend)
    initial = len(added)
    c.discover()
    assert len(added) == initial
    c.data["new"] = {
        "device": {"interfaces": [{"id": 3}]},
        "detail": {"wan_quality_by_wan": {"3": {"stat": [{"lms": 21, "ts": 2}]}}},
    }
    c.discover()
    assert any(isinstance(e, PeplinkWanQuality) and e.native_value == 21 for e in added)
    count = len(added)
    c.discover()
    assert len(added) == count


async def test_newest_survey_and_empty_not_zero(coordinator):
    coordinator.data = {
        "k": {
            "detail": {
                "tower_scans": {
                    "id": [
                        {"start_time": 9, "cellular_tower_scan": [1]},
                        {"start_time": 10, "cellular_tower_scan": [1, 2]},
                    ]
                }
            }
        }
    }
    entity = PeplinkSensor(coordinator, "k", "tower_count")
    assert entity.native_value == 2
    coordinator.data["k"]["detail"]["tower_scans"] = {"id": []}
    assert entity.native_value is None
    coordinator.data["k"]["detail"]["tower_scans"] = {"id": [{"cellular_tower_scan": []}]}
    assert entity.native_value == 0


def test_sample_reduction_keeps_older_sparse_fields():
    samples = [{"ts": t, "rsrp": -80} for t in range(10000)]
    samples[0]["carrier_name"] = "Example"
    samples[1]["lms"] = 20
    reduced = retain_samples(samples)
    assert len(reduced) <= 12
    assert any(r.get("carrier_name") == "Example" for r in reduced)
    assert any(r.get("lms") == 20 for r in reduced)
    assert reduced[-1]["ts"] == 9999
    assert latest_survey({"id": [None, {"start_time": "10"}, {"start_time": "9"}]})["start_time"] == "10"


async def test_diagnostics_allowlist(coordinator):
    coordinator.data = {
        "secret-id": {
            "device": {"name": "PRIVATE", "sn": "PRIVATE"},
            "detail": {"location": {"la": 12}, "report_status": "complete"},
        }
    }
    coordinator.hass.data[DOMAIN] = {"test": coordinator}
    result = await async_get_config_entry_diagnostics(coordinator.hass, SimpleNamespace(entry_id="test"))
    assert result["device_count"] == 1
    assert "PRIVATE" not in str(result) and "secret-id" not in str(result) and "location" not in result


class Response:
    def __init__(self, data, status=200, headers=None):
        self.data, self.status, self.headers = data, status, headers or {}
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        yield json.dumps(self.data).encode()


class Session:
    def __init__(self, replies):
        self.replies, self.posts, self.gets = iter(replies), 0, 0

    def post(self, *args, **kwargs):
        self.posts += 1
        return Response({"access_token": "synthetic", "expires_in": 3600})

    def get(self, *args, **kwargs):
        self.gets += 1
        assert kwargs["allow_redirects"] is False
        return next(self.replies)


async def test_oauth_refresh_once():
    session = Session([Response({}, 401), Response({"resp_code": "SUCCESS", "data": []})])
    client = IC2Client(session, "test", "synthetic")
    assert await client.get("/rest/o") == []
    assert session.posts == 2


async def test_rate_limit_stops_followup_requests():
    session = Session([Response({}, 429, {"Retry-After": "120"})])
    client = IC2Client(session, "test", "synthetic")
    for _ in range(2):
        with pytest.raises(IC2RateLimitError):
            await client.get("/rest/o")
    assert session.gets == 1


@pytest.mark.parametrize("data", [[], None, "bad", {"resp_code": "INVALID_INPUT"}])
async def test_invalid_response_has_safe_error(data):
    client = IC2Client(Session([Response(data)]), "test", "synthetic")
    with pytest.raises(IC2Error):
        await client.get("/rest/o")


async def test_pending_is_not_empty_list():
    client = IC2Client(Session([Response({"resp_code": "PENDING"})]), "test", "synthetic")
    assert await client.get("/rest/o") is None
