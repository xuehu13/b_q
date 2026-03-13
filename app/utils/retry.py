from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")



def retry(times: int, delay_sec: float = 1.0) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs):
            last_error: Exception | None = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt >= times:
                        raise
                    time.sleep(delay_sec)
            if last_error:
                raise last_error
            raise RuntimeError("retry exhausted")

        return wrapper

    return decorator
