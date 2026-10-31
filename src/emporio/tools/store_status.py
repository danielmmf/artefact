from datetime import datetime
from typing import Callable
from emporio.clock import make_clock
from emporio.config import Settings
from emporio.rules.hours import store_hours
from emporio.tools.contracts import ToolResult


def store_status(clock: Callable[[], datetime] | None = None) -> ToolResult:
    clock = clock if clock is not None else make_clock(Settings.from_env())
    return ToolResult(ok=True, data=store_hours(clock()))
