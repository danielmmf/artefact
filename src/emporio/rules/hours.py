from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('America/Campo_Grande')

def store_hours(now: datetime) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('Horário deve incluir fuso')
    local = now.astimezone(ZONE)
    weekday = local.weekday()
    opening = time(9)
    closing = time(18) if weekday < 5 else time(13) if weekday == 5 else None
    current = local.timetz().replace(tzinfo=None)
    is_open = closing is not None and opening <= current < closing
    if closing is not None and current < opening:
        next_opening = datetime.combine(local.date(), opening, ZONE)
    else:
        next_date = local.date() + timedelta(days=1)
        while next_date.weekday() == 6:
            next_date += timedelta(days=1)
        next_opening = datetime.combine(next_date, opening, ZONE)
    return {'now_local': local.isoformat(), 'is_open': is_open,
            'today_hours': {'open': '09:00', 'close': closing.strftime('%H:%M')} if closing else None,
            'next_opening': next_opening.isoformat(), 'holidays_considered': False}
