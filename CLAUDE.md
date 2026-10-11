# Eufy Clean maintenance guide

Home Assistant custom component, domain `robovac_mqtt`, installed through HACS.
Entities read `EufyCleanCoordinator.data` and send commands through
`build_device_command()` / `async_send_command()`. The coordinator selects the
transport and supplies the model/protocol context. Avoid calling a generic
builder directly from entities when that would lose this context.

## Active architecture

- `api/http.py` and `api/cloud.py`: Eufy login and device discovery.
- `api/client.py`: MQTT transport; `api/local_tuya.py`: the local Tuya socket;
  `api/tuya_cloud.py`: Tuya Cloud polling, commands and fresh RTC sessions.
- `api/commands.py`, `api/legacy_commands.py`: protocol-specific builders.
  `api/parser.py`, `api/parser_scalar.py`, `api/legacy_parser.py`: inbound state.
- `models.py`: `VacuumState` and received-field capability tracking.
- `coordinator.py`: lifecycle, storage, state updates, map rendering and debounce.
- `api/map_stream.py`: MQTT map parsing and bounded LZ4 decoding.
  `api/map_render.py`: the shared renderer and coordinate convention.
- `api/p2p/`: local signaling, ICE, KCP, map and H.265 decoding.
  `p2p_map.py`: supervised map sessions and persistence.
  `video_stream.py`: on-demand camera sessions and the ffmpeg JPEG pipeline.
- Entity platforms: vacuum, sensor, select, switch, number, button, binary sensor,
  time and camera. `frontend/eufy-clean-card.js` is the bundled room/zone card.

The older MQTT architecture is described in `docs/ARCHITECTURE.md`. Current
Tuya/P2P details and evidence are in `docs/P2P_MAP_CHANNEL.md` and
`docs/REVIEW_AND_VALIDATION.md`. Treat source constants and protobuf descriptors
as the canonical field/enum definitions, not duplicated tables in notes.

## Protocol and lifecycle constraints

- Device API types are novel/protobuf, scalar and legacy. Entity capability
  gating is in `entity.py`; do not expose unsupported controls by guessing.
- DPS numbers do not guarantee the same wire type across transports. Tuya
  protobuf robots use a suction enum string and a separate BoostIQ boolean.
- S1 Pro T2080A manual direction uses the V2 normal envelope. Other models keep
  their existing format. Enter manual mode explicitly; drive calls are bounded,
  finite, mutually exclusive and always end with a brake. Brake interrupts a run.
- Camera availability requires the read-only physical switch and raw mode 6.
  HA maps mode 6 to `cleaning`; that activity string must not activate the normal
  moving-map retry loop. Viewing never enters, renews or exits manual mode.
- Map and camera sessions share one exclusive slot. Cancel and await transport
  and decoder tasks before releasing it. Stop video before stopping the feed and
  before disconnecting the local client during integration unload.
- Fetch an RTC config immediately before each session. Use its reserved session
  identity and keep its credentials in memory only; never reuse or persist it.
- Respect refusal/quick-failure cooldowns even when activity changes. Do not
  restore diagnostic retry ladders or generate fallback session identities.
- Only the verified channel-0 HD startup sequence is active. Expired/cached
  images must not escape the physical-switch/manual-mode/freshness guards.
- Preserve MQTT, scalar and legacy compatibility when modifying shared parsing,
  rendering, command building or entity setup.
- Map coordinates are centimetres, grid resolution normally 5 cm; rendered PNGs
  are Y-flipped. Room id 0 is valid. No room is `None` internally / -1 in the
  room-at-point service. A new map must not reuse old geometry, rooms or motion.

## Quality and privacy rules

- Define each command/state vocabulary once and derive options from it.
- Keep protocol experiments in notes and local probes, outside shipped runtime.
  Remove unused constants, setters and state rather than retaining them for
  possible future features. Bundled generated protobuf schemas are retained.
- Test behavior at its owning module; use synthetic credentials and data.
  Do not duplicate a scenario under an unrelated test module.
- Never log credentials, RTC keys or complete signaling offers. Live home images
  require the owner's publication permission; the PR screenshots have it.
- Generated `*_pb2.py` / `*.pyi` files are bundled, not built at integration
  startup. Keep descriptors, stubs and source schemas consistent when changed.
- `pyproject.toml` is tooling metadata, not a pip-installable integration.
  `uv run pytest` runs tests; `uv run pre-commit run --all-files` runs required
  checks. CI/tooling use Python 3.14. Run those checks before pushing.
- Prefer an offline replay or a standalone Python check to a full HA restart.
  Record which build was live-tested; do not claim an undeployed cleanup was
  exercised through HA.
