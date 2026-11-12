"""Native DevArch Hermes demo. Exits 0 only when the run finishes in under 90 seconds.

Uses a temporary profile and a five-commit repository. Does not install packages,
update Hermes, or talk to a gateway.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIMIT_SECONDS = 90
PLUGIN_INIT = Path(__file__).resolve().parents[1] / "__init__.py"


class _Ctx:
    def __init__(self) -> None:
        self.hooks: dict[str, object] = {}
        self.tools: dict[str, object] = {}
        self.commands: dict[str, object] = {}

    def get_config(self, key: str, default: object = None) -> object:
        return None

    def register_hook(self, name: str, fn: object) -> None:
        self.hooks[name] = fn

    def register_command(
        self, name: str, handler: object, description: str = "", args_hint: str = ""
    ) -> None:
        self.commands[name] = handler

    def register_tool(self, **kwargs: object) -> None:
        self.tools[str(kwargs["name"])] = kwargs["handler"]

    def register_skill(self, name: str, path: Path) -> None:
        return None


def _load_plugin():
    spec = importlib.util.spec_from_file_location("devarch_hermes_plugin", PLUGIN_INIT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load plugin from {PLUGIN_INIT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def _repo(path: Path) -> None:
    path.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Demo Author",
            "GIT_AUTHOR_EMAIL": "demo@example.com",
            "GIT_COMMITTER_NAME": "Demo Author",
            "GIT_COMMITTER_EMAIL": "demo@example.com",
        }
    )
    _git(path, "init")
    _git(path, "config", "user.email", "demo@example.com")
    _git(path, "config", "user.name", "Demo Author")
    commits = [
        ("2026-01-01T12:00:00", "start"),
        ("2026-01-02T12:00:00", "early"),
        ("2026-01-03T12:00:00", "continue"),
        ("2026-02-20T12:00:00", "after gap"),
        ("2026-02-21T12:00:00", "follow up"),
    ]
    for index, (stamp, message) in enumerate(commits):
        (path / f"f{index}.txt").write_text(message + "\n", encoding="utf-8")
        _git(path, "add", f"f{index}.txt")
        commit_env = env.copy()
        commit_env["GIT_AUTHOR_DATE"] = stamp
        commit_env["GIT_COMMITTER_DATE"] = stamp
        _git(path, "commit", "-m", message, env=commit_env)


def main() -> int:
    started = time.perf_counter()
    home = Path(tempfile.mkdtemp(prefix="devarch-demo-"))
    try:
        os.environ["HERMES_HOME"] = str(home)
        plugin = _load_plugin()
        ctx = _Ctx()
        plugin.register(ctx)
        if ctx.hooks.get("post_tool_call") is not plugin._on_post_tool:
            print("report hook was not registered", file=sys.stderr)
            return 1
        if ctx.hooks.get("pre_llm_call") is not plugin._on_pre_llm:
            print("pre_llm hook was not registered", file=sys.stderr)
            return 1
        brief = plugin._on_pre_llm(user_message="How did this codebase evolve?")
        if not isinstance(brief, dict) or "archaeology" not in brief.get("context", "").lower():
            print(f"archaeology brief missing: {brief!r}", file=sys.stderr)
            return 1
        if plugin._on_pre_llm(user_message="hello there") is not None:
            print("unrelated message was given an archaeology brief", file=sys.stderr)
            return 1

        repo = home / "repo"
        _repo(repo)
        slash = ctx.commands["devarch"]
        # shlex.split treats backslashes as escapes. Quote so Windows paths survive.
        piped = slash("pipeline " + shlex.quote(str(repo)) + " demo")
        database = plugin._project_dir("demo") / "data" / "archaeology.db"
        if not database.is_file():
            print(piped, file=sys.stderr)
            return 1
        reported = slash("report demo")
        if "DevArch report" not in reported:
            print(reported, file=sys.stderr)
            return 1
        status = slash("status")
        if "devarch_report" not in status or "devarch_pipeline" not in status:
            print(status, file=sys.stderr)
            return 1
        declared = (PLUGIN_INIT.parent / "plugin.yaml").read_text(encoding="utf-8")
        if "post_tool_call" not in declared or "pre_llm_call" not in declared:
            print("plugin.yaml is missing native hooks", file=sys.stderr)
            return 1
        elapsed = time.perf_counter() - started
        print(f"elapsed_seconds={elapsed:.3f}")
        print("report_hook=wired")
        print("hooks=pre_llm_call,post_tool_call")
        print("plugin_yaml=native")
        if elapsed >= LIMIT_SECONDS:
            print(f"demo exceeded {LIMIT_SECONDS} seconds", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
