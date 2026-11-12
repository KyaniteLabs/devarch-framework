"""Keep plugin tests from shadowing the framework archaeology package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _purge_vendor_archaeology() -> None:
    """Remove the plugin dir from sys.path and drop vendored archaeology modules."""
    plugin = _PLUGIN_DIR.resolve()
    kept: list[str] = []
    for entry in sys.path:
        try:
            if Path(entry).resolve() == plugin:
                continue
        except (OSError, RuntimeError):
            pass
        kept.append(entry)
    sys.path[:] = kept

    for key in list(sys.modules):
        if key == "archaeology" or key.startswith("archaeology."):
            mod = sys.modules.get(key)
            filename = getattr(mod, "__file__", "") or ""
            if "plugins/devarch-hermes" in filename.replace("\\", "/"):
                del sys.modules[key]


def _ensure_framework_archaeology() -> Path:
    _purge_vendor_archaeology()
    import archaeology

    path = Path(archaeology.__file__).resolve()
    if "plugins/devarch-hermes" in str(path).replace("\\", "/"):
        # Still shadowed somehow — force reimport after another purge.
        _purge_vendor_archaeology()
        for key in list(sys.modules):
            if key == "archaeology" or key.startswith("archaeology."):
                del sys.modules[key]
        import archaeology as archaeology_retry

        path = Path(archaeology_retry.__file__).resolve()
    if "plugins/devarch-hermes" in str(path).replace("\\", "/"):
        raise RuntimeError(f"framework archaeology still shadowed at {path}")
    return path


def pytest_configure(config: pytest.Config) -> None:
    _ensure_framework_archaeology()


@pytest.fixture(autouse=True)
def _framework_archaeology_isolation():
    _ensure_framework_archaeology()
    yield
    _ensure_framework_archaeology()
