"""One work-kind classifier for every analysis.

A commit subject maps to one kind: feat, fix, refactor, docs, ops, test or
other. Conventional-commit prefixes win; otherwise word-bounded verbs decide.
Reverts count as fixes. Merge commits are bookkeeping and get their own flag
so analyses can leave them out.

The AG4TE Hermes plugin carries the same rules (plugins/ag4te-hermes,
``kind_of``); keep the two in step until the plugin imports this module.
"""
from __future__ import annotations

import re

KINDS = ("feat", "fix", "refactor", "docs", "ops", "test", "other")

_PREFIX_KIND = {
    "feat": "feat", "feature": "feat", "add": "feat",
    "fix": "fix", "bugfix": "fix", "hotfix": "fix",
    "refactor": "refactor", "perf": "refactor", "style": "refactor", "cleanup": "refactor",
    "docs": "docs", "doc": "docs",
    "test": "test", "tests": "test",
    "chore": "ops", "ci": "ops", "build": "ops", "deps": "ops", "release": "ops", "revert": "fix",
    "ops": "ops", "infra": "ops",
}
_CONVENTIONAL_RE = re.compile(r"^\s*([A-Za-z]+)(?:\([^)]*\))?!?\s*:")
_AREA_RE = re.compile(r"^\s*[\w./-]{1,30}:\s+")
_REVERT_RE = re.compile(r'^\s*(revert\b|revert:|Revert ")', re.I)
_MERGE_MSG_RE = re.compile(r"^\s*merge (pull request|branch|remote-tracking|tag)\b", re.I)
_WORD_KIND = (
    (re.compile(r"^\s*(bump|upgrade|release|version)\b", re.I), "ops"),
    (re.compile(r"^\s*(fix|fixes|fixed|repair|resolve|hotfix|correct)\b", re.I), "fix"),
    (re.compile(r"^\s*(refactor|rename|move|extract|simplify|clean|tidy|restructure)\b", re.I), "refactor"),
    (re.compile(r"^\s*(test|tests|cover)\b", re.I), "test"),
    (re.compile(r"\b(readme|docs?|changelog|documentation)\b", re.I), "docs"),
    (re.compile(r"^\s*(add|adds|added|implement|introduce|create|support|new|feat)\b", re.I), "feat"),
)


def is_merge(message: str) -> bool:
    """True for merge-commit subjects ("Merge pull request …", "Merge branch …")."""
    return bool(_MERGE_MSG_RE.match(message or ""))


def is_revert(message: str) -> bool:
    return bool(_REVERT_RE.match(message or ""))


def kind_of(message: str) -> str:
    """The kind of work a commit subject describes."""
    msg = message or ""
    if _REVERT_RE.match(msg):
        return "fix"
    m = _CONVENTIONAL_RE.match(msg)
    if m:
        kind = _PREFIX_KIND.get(m.group(1).lower())
        if kind:
            return kind
    for text in (msg, _AREA_RE.sub("", msg, count=1)):
        for rx, kind in _WORD_KIND:
            if rx.search(text):
                return kind
    return "other"


def word_pattern(keywords: list[str]) -> re.Pattern[str]:
    """A case-insensitive, word-bounded alternation of ``keywords``."""
    return re.compile(r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b", re.I)
