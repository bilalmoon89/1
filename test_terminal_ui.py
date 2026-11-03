"""Offline checks for the new single-screen workflow."""
from streamlit.testing.v1 import AppTest


def test_terminal_saves_candidate_and_opens_monitor():
    app = AppTest.from_file('app.py', default_timeout=90).run()
    assert not app.exception
    assert not app.tabs
    assert 'The Watchtower' in [x.value for x in app.subheader]
    assert not any(x.label == 'Workspace' for x in app.selectbox)
    choices = [x for x in app.button if x.label == 'Add to The Watchtower' and not x.disabled]
    assert choices
    choices[0].click().run()
    assert not app.exception
    assert len(app.session_state['frozen']) == 1
    assert 'Focused setup review' in [x.value for x in app.subheader]
