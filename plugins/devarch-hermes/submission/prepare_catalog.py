"""Prepare artifacts only; never push, open a PR, merge or publish."""

import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--sha", required=True, help="Exact accepted merge SHA (candidate SHA only for rehearsal)"
)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
    parser.error("--sha must be the literal full 40-character lowercase commit SHA")
entry = {
    "name": "devarch",
    "title": "DevArch — evidence before edits",
    "repo": "https://github.com/KyaniteLabs/devarch-framework",
    "sha": args.sha,
    "subdir": "plugins/devarch-hermes",
    "version": "0.1.0",
    "description": "Disclosure — vendors DevArch v0.4.1 plus reviewed patches; installs pinned click/sqlite-utils/datasette from PyPI. Calls Python APIs; framework internals run local Git and python -m sqlite_utils, inheriting the host environment. No model call, key, telemetry or invocation-time fetch. Rejects shallow/promisor/missing-object clones; Git transports and lazy fetch disabled. Reads target history; writes extracted data, SQLite, reports, locks and summary ledger under profile plugin-data/devarch. Optional HTML browser viewing can request shared web fonts; Markdown is offline. Native pre-LLM archaeology brief and post-tool ledger, slash workflow and bundled skill; capped sample/ref coverage explicit; vectors are leads and gap clusters are not curated eras.",
    "maintainer": "KyaniteLabs",
    "tier": "community",
    "category": "tools",
    "requires_hermes": ">=0.21.6",
    "docs_url": f"https://github.com/KyaniteLabs/devarch-framework/blob/{args.sha}/plugins/devarch-hermes/README.md",
    "platforms": [],
    "capabilities": {
        "provides_tools": [
            "devarch_mine",
            "devarch_signals",
            "devarch_report",
            "devarch_pipeline",
            "devarch_list",
            "devarch_version",
        ],
        "provides_hooks": ["pre_llm_call", "post_tool_call"],
        "provides_middleware": [],
        "requires_env": [],
    },
}
args.out.mkdir(parents=True, exist_ok=True)
# JSON is YAML 1.2; avoids adding a runtime YAML writer dependency to the plugin.
(args.out / "devarch.yaml").write_text(json.dumps(entry, indent=2) + "\n")
print(args.out / "devarch.yaml")
