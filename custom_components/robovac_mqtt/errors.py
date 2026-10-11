"""Model-specific screen codes and shared HA error attributes.

S1 Pro mappings are factual code pairs from eufy Clean 3.20.0 (1042),
assets/green_lantern/T2080A_prompt_json.json and English string resources.
The older protobuf enum named t2080 uses a different numbering scheme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import VacuumState

S1_PRO_MODELS = frozenset({"T2080", "T2080A"})

_S1_PRO_SCREEN_CODES = {
    18875652: "E54",
    18876163: "E73",
    18876178: "E7J",
    18939904: "EB00",
    18939905: "EB01",
    18940175: "EB1F",
    18940176: "EB1G",
    18940177: "EB1H",
    19922944: "E0",
    19922945: "E1",
    19922947: "E3",
    19923200: "E10",
    19923202: "E12",
    19923204: "E14",
    19923206: "E16",
    19923712: "E30",
    19923713: "E31",
    19924225: "E51",
    19924229: "E55",
    19924230: "E56",
    19924231: "E57",
    19924233: "E59",
    19924240: "E5G",
    19924241: "E5H",
    19924736: "E70",
    19924738: "E72",
    19924740: "E74",
    19924741: "E75",
    19924742: "E76",
    19924743: "E77",
    19924755: "E7K",
    19988736: "EB10",
    19988737: "EB11",
    19988738: "EB12",
    19988739: "EB13",
    19988740: "EB14",
    19988741: "EB15",
    19988754: "EB1J",
    19988755: "EB1K",
    19989253: "EB35",
    20971522: "E2",
    20971524: "E4",
    20971527: "E7",
    20971779: "E13",
    20971781: "E15",
    20972032: "E20",
    20972033: "E21",
    20972034: "E22",
    20972035: "E23",
    20972037: "E25",
    20972290: "E32",
    20972545: "E41",
    20972800: "E50",
    20972802: "E52",
    20972803: "E53",
    20972808: "E58",
    20972810: "E5A",
    20972811: "E5B",
    20972812: "E5C",
    20972813: "E5D",
    20973333: "E7M",
    21037058: "EB02",
    21037059: "EB03",
    21037318: "EB16",
    21037319: "EB17",
    21037320: "EB18",
    21037321: "EB19",
    21037323: "EB1B",
    21037324: "EB1C",
    21037568: "EB20",
    21037569: "EB21",
    21037571: "EB23",
    21037572: "EB24",
    21037824: "EB30",
    21037825: "EB31",
    21037826: "EB32",
    21037827: "EB33",
    21037828: "EB34",
    21037830: "EB36",
    21037831: "EB37",
    21038081: "EB41",
}

_S1_PRO_DESCRIPTIONS = {
    "E0": "Dustbin or filter not installed",
    "E1": "Roller brush blocked",
    "E30": "Robot lifted off the ground",
    "E31": "Drive wheel blocked",
    "E74": "Return to base station failed",
    "E75": "Return to base station failed: route blocked",
    "E76": "Return to base station failed: task ended",
    "E77": "Robot not detected at the base station: task paused",
    "EB11": "Base station clean water low",
    "EB13": "Base station dirty water tank full",
}


def screen_error_code(code: int, model: str) -> str | int:
    """Return a verified screen code, keeping other models/numbers unchanged."""
    if model.upper() in S1_PRO_MODELS:
        return _S1_PRO_SCREEN_CODES.get(code, code)
    return code


def s1_error_message(code: int, model: str) -> str | None:
    """Describe a verified S1 code without guessing another model's mapping."""
    label = screen_error_code(code, model)
    if isinstance(label, str):
        return _S1_PRO_DESCRIPTIONS.get(label, f"Robot fault ({label})")
    return None


def error_attributes(state: VacuumState) -> dict[str, Any]:
    """Expose current errors and the previous error without losing raw numbers."""
    return {
        "error_code": screen_error_code(state.error_code, state.device_model),
        "error_code_raw": state.error_code,
        "error_codes": [screen_error_code(c, state.device_model) for c in state.error_codes],
        "error_codes_raw": list(state.error_codes),
        "error_active": state.activity == "error" and bool(state.error_code),
        "last_error_code": screen_error_code(state.last_error_code, state.device_model),
        "last_error_code_raw": state.last_error_code,
        "last_error_message": state.last_error_message,
    }


def error_sensor_value(state: VacuumState) -> str:
    """A short error code suitable for HA state triggers."""
    return str(screen_error_code(state.error_code, state.device_model)) if state.error_code else "None"
