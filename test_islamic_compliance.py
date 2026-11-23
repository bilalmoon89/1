import json
from datetime import date
from islamic_compliance import compliance_box, SNAPSHOT
from terminal_view import header


def test_snapshot_has_250_verified_rows_and_requested_labels():
    data = json.loads(SNAPSHOT.read_text())
    assert len(data['stocks']) == 250
    for symbol, expected in [('AAPL', 'Compliant'), ('MSFT', 'Questionable'), ('ANF', 'Non Compliant'), ('NOTFOUND', 'No Data'), ('SPY','No Data')]:
        html = compliance_box(symbol, date(2026,11,23), data)
        assert f'<b>{expected}</b>' in html
        assert 'Reference:' in html
        assert 'For information and idea generation only.' in html
        assert 'Verify current compliance before acting.' in html
        assert 'Data provided by Zoya' not in html


def test_rating_expires_at_15_days_and_future_snapshot_is_not_used():
    assert '<b>Compliant</b>' in compliance_box('AAPL', date(2026,12,7))
    assert '<b>No Data</b>' in compliance_box('AAPL', date(2026,12,8))
    assert 'Refresh overdue' in compliance_box('AAPL', date(2026,12,8))
    assert '<b>No Data</b>' in compliance_box('AAPL', date(2026,11,22))


def test_unknown_status_not_assumed_compliant_and_dates_escaped():
    data = {'methodology':'AAOIFI','checked_on':'2026-11-23','stocks':{'X':{'status':'NewValue','report_date':'2026-11-01'}}}
    assert '<b>No Data</b>' in compliance_box('X', date(2026,11,23), data)
    data['stocks']['X']['report_date'] = '<script>alert(1)</script>'
    assert '<script>' not in compliance_box('X', date(2026,11,23), data)


def test_navigation_places_ticker_immediately_after_rotation():
    html = header()
    assert html.index('view=rotation') < html.index('view=ticker') < html.index('view=setups')
