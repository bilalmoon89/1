"""Read-only Zoya AAOIFI snapshot. Missing/expired ratings never imply compliance."""
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from html import escape

SNAPSHOT = Path(__file__).with_name('zoya_snapshot.json')
LABELS = {'Compliant': ('Compliant', 'pass'), 'Questionable': ('Questionable', 'warn'),
          'NonCompliant': ('Non Compliant', 'fail')}


def compliance_box(symbol, today=None, snapshot=None):
    today = today or datetime.now(ZoneInfo('America/New_York')).date()
    if snapshot is None:
        try:
            snapshot = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            snapshot = {}
    row = snapshot.get('stocks', {}).get(symbol, {})
    label, tone = 'No Data', 'na'
    reference = row.get('report_date', '—')
    note = 'No saved report for this listing.'
    try:
        checked = date.fromisoformat(row.get('checked_on') or snapshot['checked_on'])
        report = date.fromisoformat(row['report_date'])
        due = checked + timedelta(days=15)
        if checked <= today < due and report <= checked and snapshot.get('methodology') == 'AAOIFI':
            label, tone = LABELS.get(row.get('status'), ('No Data', 'na'))
            note = f'Checked {checked} · refresh by {due}'
        elif today >= due:
            note = f'Refresh overdue since {due}; saved rating withheld.'
        else:
            note = 'Snapshot dates or methodology could not be verified.'
    except (KeyError, ValueError, TypeError):
        pass
    e = lambda value: escape(str(value), quote=True)
    return (f'<aside class="tc-islamic {tone}" aria-label="Islamic compliance">'
            '<small>ISLAMIC COMPLIANCE · AAOIFI</small>'
            f'<b>{e(label)}</b><span>Reference: {e(reference)}</span>'
            f'<small title="Saved stock screening; not an options-strategy ruling">{e(note)}</small>'
            '<small>For information and idea generation only. Verify current compliance before acting.</small></aside>')
