from __future__ import annotations

from datetime import datetime, timezone



def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)



def ms_to_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
