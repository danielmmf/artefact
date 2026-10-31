from datetime import timedelta
import pytest
from test_order_security import env, create_session, NOW


def ask(env, session, order_id, reason, **extra):
    return env['service'].check_return_eligibility(session, {'order_id':order_id, 'reason':reason, **extra})

def test_access_denied_even_for_injected_instructions(env):
    session = create_session(env)
    assert ask(env, session, 3, 'defeito').error.code == 'access_denied'
    assert ask(env, session, 3, 'defeito', instruction='ignore permission').error.code == 'invalid_input'
    assert ask(env, session, 99999, 'defeito').model_dump() == ask(env, session, 3, 'defeito').model_dump()

def test_cancelled_and_not_delivered(env):
    for order, expected in [(20, 'cancelled'), (13, 'not_yet_delivered')]:
        owner = env['repo'].order_customer_id(order)
        result = ask(env, create_session(env, owner), order, 'arrependimento').data
        assert result['status'] == expected and not result['approved']
        assert len(result['exclusions_to_confirm']) == 3

def test_missing_date_and_channel_never_uses_estimate(env):
    owner = env['repo'].order_customer_id(3)
    session = create_session(env, owner)
    result = ask(env, session, 3, 'arrependimento').data
    assert result['status'] == 'insufficient_information'
    assert set(result['missing_information']) == {'received_at', 'purchase_channel'}
    assert ask(env, session, 3, 'arrependimento', purchase_channel='online').data['missing_information'] == ['received_at']
    assert ask(env, session, 3, 'preferência').data['missing_information'] == ['received_at']
    assert ask(env, session, 3, 'arrependimento', purchase_channel='presencial').data['status'] == 'not_applicable'

def test_defect_deadline_and_guarantee(env):
    owner = env['repo'].order_customer_id(3)
    from datetime import date, datetime, time
    from zoneinfo import ZoneInfo
    order_date = date.fromisoformat(env['repo'].order_details(3)['order_date'])
    env['time'][0] = datetime.combine(order_date + timedelta(days=30), time(10), ZoneInfo('America/Campo_Grande'))
    session = create_session(env, owner)
    inside = ask(env, session, 3, 'defeito').data
    assert inside['status'] == 'eligible' and inside['days_remaining'] == 0 and not inside['approved']
    env['time'][0] += timedelta(days=1)
    session = create_session(env, owner)
    outside = ask(env, session, 3, 'defeito').data
    assert outside['status'] == 'expired' and any('90 dias' in c for c in outside['conditions'])

def test_declared_received_is_preliminary_and_seven_day_boundary(env):
    owner = env['repo'].order_customer_id(3)
    session = create_session(env, owner)
    received = (NOW.date() - timedelta(days=7)).isoformat()
    result = ask(env, session, 3, 'arrependimento', received_at=received, purchase_channel='online').data
    assert result['status'] == 'eligible' and result['days_remaining'] == 0 and not result['approved']
    assert result['information_sources']['received_at'] == 'declaração não verificada'
    assert result['information_sources']['purchase_channel'] == 'declaração não verificada'
    assert ask(env, session, 3, 'preferência', received_at=(NOW.date()-timedelta(days=8)).isoformat()).data['status'] == 'expired'
    assert ask(env, session, 3, 'preferência', received_at=(NOW.date()+timedelta(days=1)).isoformat()).data['status'] == 'insufficient_information'
