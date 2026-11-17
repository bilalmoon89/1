"""Retry local-module invalidation races during a hosted source reload."""
import importlib
import time

LOCAL_MODULES={'terminal_view','liquid_view','liquid_app','liquid_uptrend','liquid_data','liquid_table','session_validity','ticker_check','ticker_check_app','ticker_check_view','ticker_financials',
    'crescent_engine','crescent_feeds','intraday_context','market_symbols','theme_rotation','watchtower',
    'scan_store','market_brief','brief_cards','brief_view','rotation_app','rotation_view','rotation_cards','rotation_engine','setups_app','setups_view','setup_scanner','sector_map','nyse_fallback'}


def import_local(name):
    for attempt in range(3):
        try:return importlib.import_module(name)
        except KeyError as exc:
            if not exc.args or exc.args[0] not in LOCAL_MODULES or attempt==2:raise
            # Do not clear sys.modules: another session may still be using it.
            time.sleep(.05*(attempt+1))
