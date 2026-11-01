from datetime import datetime
from functools import partial
from typing import Callable
from zoneinfo import ZoneInfo

from emporio.config import Settings


def now(fixed: str | None = None, *, real_time: Callable[[ZoneInfo], datetime] = datetime.now) -> datetime:
    result = datetime.fromisoformat(fixed) if fixed else real_time(ZoneInfo('America/Campo_Grande'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('EMPORIO_NOW deve incluir fuso horário')
    return result


def make_clock(settings: Settings, *, real_time: Callable[[ZoneInfo], datetime] = datetime.now) -> Callable[[], datetime]:
    """Compõe um relógio injetável a partir da configuração da aplicação."""
    return partial(now, settings.emporio_now, real_time=real_time)
