from datetime import datetime
from zoneinfo import ZoneInfo


def now(fixed: str | None = None) -> datetime:
    result = datetime.fromisoformat(fixed) if fixed else datetime.now(ZoneInfo('America/Campo_Grande'))
    if result.tzinfo is None:
        raise ValueError('EMPORIO_NOW deve incluir fuso horário')
    return result
