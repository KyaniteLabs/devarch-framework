#!/usr/bin/env python3
"""Mine private conversation/session exports into archaeology data files.

This replaces the earlier one-off root scripts (`mine_sessions*.py`,
`mine_liminal_sessions.py`, and `mine_gpt_conversations.py`) with a single
configurable CLI.

Examples:

  python3 scripts/mine_conversations.py claude \
    --sessions-dir ~/.claude/projects/-Users-simongonzalezdecruz-Desktop-OMC \
    --output-dir projects/liminal/data \
    --prefix sessions

  python3 scripts/mine_conversations.py claude \
    --sessions-dir ~/.claude/projects/-Users-simongonzalezdecruz-workspaces-liminal \
    --output-dir projects/liminal/data \
    --prefix liminal

  python3 scripts/mine_conversations.py chatgpt \
    --input ~/Desktop/MyStuff/Documents/ToReview/conversations.json \
    --output-dir projects/liminal/data

Private inputs are intentionally not required by `regenerate_all.py` unless
`--mine-private-sessions` is passed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "projects/liminal/data"
DEFAULT_OMC_SESSIONS = Path(os.environ.get(
    "ARCHAEOLOGY_OMC_SESSIONS",
    "~/.claude/projects/-Users-simongonzalezdecruz-Desktop-OMC",
)).expanduser()
DEFAULT_LIMINAL_SESSIONS = Path(os.environ.get(
    "ARCHAEOLOGY_LIMINAL_SESSIONS",
    "~/.claude/projects/-Users-simongonzalezdecruz-workspaces-liminal",
)).expanduser()
DEFAULT_CHATGPT_EXPORT = Path(os.environ.get(
    "ARCHAEOLOGY_CHATGPT_EXPORT",
    "~/Desktop/MyStuff/Documents/ToReview/conversations.json",
)).expanduser()

GPT_PATTERNS = [
    re.compile(r"\bGPT\b", re.IGNORECASE),
    re.compile(r"\bGPT[-\s]?5(?:\.4)?\b", re.IGNORECASE),
    re.compile(r"\bGPT[-\s]?4\b", re.IGNORECASE),
    re.compile(r"\bOpenAI\b", re.IGNORECASE),
    re.compile(r"\bChatGPT\b", re.IGNORECASE),
    re.compile(r"\bo1\b", re.IGNORECASE),
]

REFLECTION_PATTERNS = [
    re.compile(r"\bi\s+(?:just\s+)?(?:understand|see|get|realized|learned|discovered)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:really\s+)?(?:understand|see|get|realized|learned|discovered)\b", re.IGNORECASE),
    re.compile(r"\bnow\s+i\s+(?:understand|see|get|realized|learned|discovered)\b", re.IGNORECASE),
    re.compile(r"\b(?:i've|i have)\s+(?:learned|realized|discovered|figured\s+out)\b", re.IGNORECASE),
    re.compile(r"\b(?:i've|i have)\s+just\s+(?:learned|realized|discovered|figured\s+out)\b", re.IGNORECASE),
    re.compile(r"\bmy\s+(?:understanding|insight|takeaway|learning|realization|hypothesis|theory|sense|intuition)\s+(?:is|was)\b", re.IGNORECASE),
    re.compile(r"\bthe\s+(?:pattern|trend|theme)\s+(?:i'm\s+)?(?:seeing|noticing|observing)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:keep\s+)?(?:notice|observe|see)\s+(?:that\s+)?:?\s*a\s+(?:pattern|trend)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+(?:is\s+)?(?:interesting|fascinating|surprising|confusing|puzzling)\b", re.IGNORECASE),
    re.compile(r"\bthis\s+is\s+really\s+(?:interesting|fascinating|surprising|confusing|puzzling)\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:am\s+)?(?:excited|worried|concerned|surprised|confused|puzzled)\s+(?:about|that|by)\b", re.IGNORECASE),
    re.compile(r"\bi\s+think\s+(?:we\s+should|i\s+should|the\s+approach\s+should)\b", re.IGNORECASE),
    re.compile(r"\bthat\s+(?:helps|clarifies|makes\s+sense)\b", re.IGNORECASE),
    re.compile(r"\bnow\s+i\s+(?:see|get|understand)\b", re.IGNORECASE),
    re.compile(r"\bkey\s+insight\b", re.IGNORECASE),
    re.compile(r"\bbreakthrough\b", re.IGNORECASE),
]

DECISION_PATTERNS = [
    re.compile(r"\bI decided\b", re.IGNORECASE),
    re.compile(r"\bI'm going to\b", re.IGNORECASE),
    re.compile(r"\blet's pivot\b", re.IGNORECASE),
    re.compile(r"\bchange direction\b", re.IGNORECASE),
    re.compile(r"\bnew approach\b", re.IGNORECASE),
    re.compile(r"\bdecision\b", re.IGNORECASE),
]

FRUSTRATION_PATTERNS = [
    re.compile(r"\bfrustrat", re.IGNORECASE),
    re.compile(r"\bstuck\b", re.IGNORECASE),
    re.compile(r"\bannoying\b", re.IGNORECASE),
    re.compile(r"\bthis doesn't work\b", re.IGNORECASE),
    re.compile(r"\bugh\b", re.IGNORECASE),
    re.compile(r"\bargh\b", re.IGNORECASE),
]

EXCLUDE_PATTERNS = [
    re.compile(r"^<task-notification>", re.IGNORECASE),
    re.compile(r"^this\s+session\s+is\s+being\s+continued", re.IGNORECASE),
    re.compile(r"^copy/paste\s+this", re.IGNORECASE),
    re.compile(r"^DASHBOARD\s+MONITOR", re.IGNORECASE),
    re.compile(r"^PIPELINE\s+ARCHITECTURE", re.IGNORECASE),
]


def matches(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    # Skip lines longer than 5000 chars to avoid regex catastrophic backtracking
    if len(text) > 5000:
        return False
    return any(pattern.search(text) for pattern in patterns)


def is_system_or_noise(content: str, *, min_chars: int = 100) -> bool:
    stripped = content.strip()
    if len(stripped) < min_chars:
        return True
    if stripped.count("```") >= 2:
        return True
    return matches(stripped, EXCLUDE_PATTERNS)


def claude_text_parts(entry: dict[str, Any]) -> list[str]:
    message = entry.get("message", {})
    content = message.get("content") if isinstance(message, dict) else entry.get("content")
    if not content:
        return []
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") in {"tool_result", "image"}:
                    continue
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return parts
    return []


def classify_text(content: str) -> str | None:
    if matches(content, GPT_PATTERNS):
        return "gpt_conversation"
    if matches(content, REFLECTION_PATTERNS):
        return "user_reflection"
    if matches(content, DECISION_PATTERNS):
        return "decision"
    if matches(content, FRUSTRATION_PATTERNS):
        return "frustration"
    return None


def mine_claude_sessions(sessions_dir: Path, output_dir: Path, prefix: str, *, dry_run: bool) -> dict[str, int]:
    files = sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_size, reverse=True)
    results: list[dict[str, Any]] = []

    for file_path in files:
        session_id = file_path.stem
        with file_path.open(encoding="utf-8") as handle:
            for line_num, line in enumerate(handle, 1):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Skipping malformed JSON line {line_num}: {e}", file=sys.stderr)
                    continue
                if entry.get("type") != "user":
                    continue
                for content in claude_text_parts(entry):
                    if is_system_or_noise(content):
                        continue
                    kind = classify_text(content)
                    if not kind:
                        continue
                    results.append(
                        {
                            "timestamp": entry.get("timestamp", ""),
                            "session_id": session_id,
                            "type": kind,
                            "content": content,
                            "context": f"Line {line_num} in {file_path.name}",
                            "file": file_path.name,
                        }
                    )

    gpt = [row for row in results if row["type"] == "gpt_conversation"]
    non_gpt = [row for row in results if row["type"] != "gpt_conversation"]
    output_dir.mkdir(parents=True, exist_ok=True)
    gpt_path = output_dir / f"{prefix}-gpt54-extracted.json"
    reflections_path = output_dir / (
        "sessions-user-reflections-extracted.json" if prefix == "sessions" else f"{prefix}-learnings-extracted.json"
    )
    if not dry_run:
        gpt_path.write_text(json.dumps(gpt, indent=2, ensure_ascii=False) + "\n")
        reflections_path.write_text(json.dumps(non_gpt, indent=2, ensure_ascii=False) + "\n")
    return {"files": len(files), "matches": len(results), "gpt": len(gpt), "reflections": len(non_gpt)}


def chatgpt_text(content: Any) -> str:
    if not isinstance(content, dict) or content.get("content_type") != "text":
        return ""
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        return ""
    strings: list[str] = []
    for part in parts:
        if isinstance(part, str):
            strings.append(part)
        elif isinstance(part, dict) and isinstance(part.get("text"), str):
            strings.append(part["text"])
    return "\n".join(strings)


def mine_chatgpt_export(input_path: Path, output_dir: Path, *, dry_run: bool) -> dict[str, int]:
    conversations = json.loads(input_path.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for conversation in conversations:
        title = conversation.get("title", "Untitled")
        create_time = conversation.get("create_time")
        try:
            if isinstance(create_time, (int, float)):
                create_date = datetime.fromtimestamp(create_time).isoformat()
            else:
                create_date = None
        except (ValueError, TypeError, OSError):
            create_date = None
        for node_id, node in conversation.get("mapping", {}).items():
            message = node.get("message") if isinstance(node, dict) else None
            if not message:
                continue
            role = message.get("author", {}).get("role", "")
            content = chatgpt_text(message.get("content", {}))
            if not content or len(content) < 50:
                continue
            kind = "gpt_54_conversation" if matches(content, GPT_PATTERNS) else None
            if role == "user" and not kind and matches(content, REFLECTION_PATTERNS):
                kind = "simon_learning"
            if not kind:
                continue
            msg_create_time = message.get("create_time")
            try:
                if isinstance(msg_create_time, (int, float)) and msg_create_time:
                    timestamp = datetime.fromtimestamp(msg_create_time).isoformat()
                else:
                    timestamp = None
            except (ValueError, TypeError, OSError):
                timestamp = None
            results.append(
                {
                    "conversation_title": title,
                    "conversation_date": create_date,
                    "message_role": role,
                    "type": kind,
                    "content": content,
                    "node_id": node_id,
                    "timestamp": timestamp,
                }
            )

    gpt = [row for row in results if row["type"] == "gpt_54_conversation"]
    learnings = [row for row in results if row["type"] == "simon_learning"]
    output_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        (output_dir / "gpt-conversations-extracted.json").write_text(json.dumps(gpt, indent=2, ensure_ascii=False) + "\n")
        (output_dir / "simon-learnings-extracted.json").write_text(json.dumps(learnings, indent=2, ensure_ascii=False) + "\n")
    return {"conversations": len(conversations), "matches": len(results), "gpt": len(gpt), "learnings": len(learnings)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine private conversation/session exports into archaeology data files.")
    sub = parser.add_subparsers(dest="command", required=True)

    claude = sub.add_parser("claude", help="Mine Claude Code JSONL sessions")
    claude.add_argument("--sessions-dir", type=Path, default=DEFAULT_OMC_SESSIONS)
    claude.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    claude.add_argument("--prefix", default="sessions", help="Output prefix, e.g. sessions or liminal")
    claude.add_argument("--dry-run", action="store_true")

    chatgpt = sub.add_parser("chatgpt", help="Mine ChatGPT conversations.json export")
    chatgpt.add_argument("--input", type=Path, default=DEFAULT_CHATGPT_EXPORT)
    chatgpt.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    chatgpt.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "claude":
        if not args.sessions_dir.exists():
            print(f"Session directory not found: {args.sessions_dir}", file=sys.stderr)
            return 1
        stats = mine_claude_sessions(args.sessions_dir, args.output_dir, args.prefix, dry_run=args.dry_run)
    else:
        if not args.input.exists():
            print(f"ChatGPT export not found: {args.input}", file=sys.stderr)
            return 1
        stats = mine_chatgpt_export(args.input, args.output_dir, dry_run=args.dry_run)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
