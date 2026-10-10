"""Keep a live P2P map feed running for a local-Tuya robot.

The robot ends a P2P session itself after ~15 s with nothing to send, so while
it rests in the dock a session only lives long enough to deliver the map, the
rooms and the last path. While it works it streams every ~2 s for as long as the
session stays open. The supervisor therefore:

* reconnects at once (with backoff on failures) while the robot is active;
* reconnects on demand (:meth:`P2PMapFeed.poke`) when the robot changes activity
  or its map may have changed, and otherwise refreshes on a slow timer.

Decoded state is persisted so the map, rooms and last path survive a restart
before the first session completes.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

from .api.p2p import P2PError, P2PSession
from .api.p2p.mapdata import Obstacle, P2PMap, P2PMapDecoder, Pose, decode_path

_LOGGER = logging.getLogger(__name__)

_IDLE_REFRESH = 15 * 60  # docked: refresh the snapshot this often
_ACTIVE_RETRY = 2.0
_BACKOFF_MAX = 120.0
_RTC_REFRESH = 6 * 3600


class P2PMapFeed:
    """Supervises P2P sessions and folds their objects into a :class:`P2PMap`."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        local_key: str,
        device_id: str,
        rtc_config: Callable[[], Any],
        is_active: Callable[[], bool],
        on_change: Callable[[set[str]], None],
        name: str,
    ) -> None:
        self._hass = hass
        self._host = host
        self._local_key = local_key
        self._device_id = device_id
        self._rtc_config = rtc_config
        self._is_active = is_active
        self._on_change = on_change
        self._name = name
        self.decoder = P2PMapDecoder()
        self._task: asyncio.Task | None = None
        self._session: P2PSession | None = None
        self._wake = asyncio.Event()
        self._rtc: dict[str, Any] | None = None
        self._rtc_at = 0.0
        self.connected = False
        self.last_object_at: float | None = None
        self.sessions = 0
        self.failures = 0
        self.last_error: str | None = None

    @property
    def host(self) -> str:
        return self._host

    @property
    def local_key(self) -> str:
        return self._local_key

    @property
    def device_id(self) -> str:
        return self._device_id

    async def get_rtc(self) -> dict[str, Any]:
        """The P2P credentials (device password + ICE config), cached and refreshed."""
        return await self._get_rtc()

    @property
    def state(self) -> P2PMap:
        return self.decoder.state

    def start(self) -> None:
        if self._task is None:
            self._task = self._hass.async_create_background_task(
                self._supervise(), f"robovac_mqtt p2p map {self._name}"
            )

    async def stop(self) -> None:
        task, self._task = self._task, None
        if self._session is not None:
            await self._session.close()
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutting down
                pass

    def poke(self) -> None:
        """Ask for a fresh session soon (activity changed, map may have changed)."""
        self._wake.set()

    async def _get_rtc(self) -> dict[str, Any]:
        if self._rtc is None or time.monotonic() - self._rtc_at > _RTC_REFRESH:
            rtc = await self._rtc_config()
            if not rtc or not rtc.get("device_password"):
                raise P2PError("no P2P credentials from Tuya Cloud")
            self._rtc, self._rtc_at = rtc, time.monotonic()
        assert self._rtc is not None
        return self._rtc

    async def _supervise(self) -> None:
        backoff = _ACTIVE_RETRY
        while True:
            self._wake.clear()
            started = time.monotonic()
            try:
                await self._run_session()
                self.last_error = None
                backoff = _ACTIVE_RETRY
            except Exception as err:  # noqa: BLE001 - keep supervising whatever happens
                self.failures += 1
                self.last_error = str(err)
                if self._rtc is not None and "credential" in str(err).lower():
                    self._rtc = None
                _LOGGER.debug("P2P map session for %s ended: %s", self._name, err)
                if time.monotonic() - started < 30:
                    backoff = min(backoff * 2, _BACKOFF_MAX)
            finally:
                self.connected = False
                self._session = None

            delay = backoff if self._is_active() else _IDLE_REFRESH
            try:
                await asyncio.wait_for(self._wake.wait(), delay)
            except TimeoutError:
                pass

    async def _run_session(self) -> None:
        rtc = await self._get_rtc()
        self.decoder.start_session()
        self._session = P2PSession(
            host=self._host,
            local_key=self._local_key,
            device_id=self._device_id,
            device_password=rtc["device_password"],
            ice_config=rtc.get("ice_config"),
            on_object=self._on_object,
        )
        self.sessions += 1
        await self._session.run()

    def _on_object(self, name: str, obj: bytes) -> None:
        if not self.connected:
            self.connected = True
            self.last_error = None  # the channel is up again
        self.last_object_at = time.time()
        changed = self.decoder.apply(name, obj)
        if changed:
            self._on_change(changed)

    # -- persistence -------------------------------------------------------

    def dump(self) -> dict[str, Any]:
        s = self.state
        return {
            "map_id": s.map_id,
            "width": s.width,
            "height": s.height,
            "origin": [s.origin_x, s.origin_y],
            "docks": [[d.x, d.y, d.theta] for d in s.docks],
            "outline": base64.b64encode(s.outline).decode() if s.outline else None,
            "rooms": s.rooms,
            "obstacles": [
                {"type": o.object_type, "points": [list(p) for p in o.points], "photo_id": o.photo_id}
                for o in s.obstacles
            ],
            "virtual_walls": [[list(a), list(b)] for a, b in s.virtual_walls],
            "forbidden_zones": [[list(p) for p in q] for q in s.forbidden_zones],
            "ban_mop_zones": [[list(p) for p in q] for q in s.ban_mop_zones],
            "path": base64.b64encode(
                b"".join(
                    int(x).to_bytes(2, "big", signed=True)
                    + int(y).to_bytes(2, "big", signed=True)
                    + bytes([f & 0xFF])
                    for x, y, f in s.path
                )
            ).decode(),
            "pose": [s.pose.x, s.pose.y, s.pose.theta] if s.pose else None,
        }

    def restore(self, data: dict[str, Any]) -> None:
        try:
            s = P2PMap(
                map_id=data["map_id"],
                width=data["width"],
                height=data["height"],
                origin_x=data["origin"][0],
                origin_y=data["origin"][1],
                docks=[Pose(*d) for d in data.get("docks", [])],
                outline=base64.b64decode(data["outline"]) if data.get("outline") else None,
                rooms=list(data.get("rooms", [])),
                obstacles=[
                    Obstacle(o["type"], tuple(tuple(p) for p in o["points"]), photo_id=o.get("photo_id", ""))
                    for o in data.get("obstacles", [])
                ],
                virtual_walls=[(tuple(a), tuple(b)) for a, b in data.get("virtual_walls", [])],
                forbidden_zones=[[tuple(p) for p in q] for q in data.get("forbidden_zones", [])],
                ban_mop_zones=[[tuple(p) for p in q] for q in data.get("ban_mop_zones", [])],
                path=decode_path(base64.b64decode(data.get("path") or "")),
                pose=Pose(*data["pose"]) if data.get("pose") else None,
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Ignoring unreadable stored P2P map for %s: %s", self._name, err)
            return
        self.decoder = P2PMapDecoder(s)
