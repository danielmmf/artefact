from datetime import datetime
import pytest
from emporio.tools.store_status import store_status

@pytest.mark.parametrize(('date', 'is_open', 'next_open'), [
    ('2026-03-28T12:59:00-04:00', True, '2026-03-30T09:00:00-04:00'),
    ('2026-03-28T13:00:00-04:00', False, '2026-03-30T09:00:00-04:00'),
    ('2026-03-29T11:00:00-04:00', False, '2026-03-30T09:00:00-04:00'),
    ('2026-03-30T08:59:00-04:00', False, '2026-03-30T09:00:00-04:00'),
    ('2026-03-30T09:00:00-04:00', True, '2026-03-31T09:00:00-04:00'),
    ('2026-03-30T17:59:00-04:00', True, '2026-03-31T09:00:00-04:00'),
    ('2026-03-30T18:00:00-04:00', False, '2026-03-31T09:00:00-04:00'),
])
def test_boundaries(date, is_open, next_open):
    result = store_status(lambda: datetime.fromisoformat(date)).data
    assert result['is_open'] is is_open
    assert result['next_opening'] == next_open

def test_environment_clock(monkeypatch):
    monkeypatch.setenv('EMPORIO_NOW', '2026-03-28T13:00-04:00')
    assert store_status().data['is_open'] is False

def test_different_timezone_and_naive():
    assert store_status(lambda: datetime.fromisoformat('2026-03-28T16:59:00+00:00')).data['is_open'] is True
    with pytest.raises(ValueError):
        store_status(lambda: datetime(2026, 3, 28, 12, 0))
