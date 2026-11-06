"""Retry local-module invalidation races during a hosted source reload."""
import importlib
import time

LOCAL_MODULES={'terminal_view','liquid_view','liquid_app','liquid_uptrend','liquid_data','liquid_table','session_validity',
    'crescent_engine','crescent_feeds','intraday_context','market_symbols','theme_rotation','watchtower'}


def import_local(name):
    for attempt in range(3):
        try:return importlib.import_module(name)
        except KeyError as exc:
            if not exc.args or exc.args[0] not in LOCAL_MODULES or attempt==2:raise
            # Do not clear sys.modules: another session may still be using it.
            time.sleep(.05*(attempt+1))
