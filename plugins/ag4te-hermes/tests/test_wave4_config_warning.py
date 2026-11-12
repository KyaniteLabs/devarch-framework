"""A settings read that raises falls back to the default and says so once, not silently."""

import importlib.util
import logging
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def test_failing_config_read_warns_once_and_uses_the_default():
    spec = importlib.util.spec_from_file_location("ag4te_w4_cfg", PKG / "__init__.py")
    ag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ag)

    class BrokenCtx:
        def get_config(self, key, default=None):
            raise RuntimeError("config store unreadable at /home/ada/.hermes")

    ag._ctx = BrokenCtx()
    key = next(iter(ag.DEFAULTS))
    caplog = []
    handler = logging.Handler()
    handler.emit = caplog.append
    ag.logger.addHandler(handler)
    try:
        first = ag._cfg(key)
        second = ag._cfg(key)
        ag._cfg(next(iter(list(ag.DEFAULTS)[1:])))
    finally:
        ag.logger.removeHandler(handler)
        ag._ctx = None
    assert first == second == ag.DEFAULTS[key]
    warnings = [r for r in caplog if r.levelno == logging.WARNING and "config" in r.getMessage()]
    assert len(warnings) == 1
    assert "/home/ada" not in warnings[0].getMessage()
