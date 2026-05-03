#!/usr/bin/env python3
# Extracted from Liminal's archaeology pipeline (narrative/extract_sessions.py)
"""
Extract narrative material from all Claude Code JSONL session files.
V2: Better filtering of tool-result noise, focus on genuine dialogue.
V3: Project-agnostic -- accepts --sessions-dir, --output, --config, --project args.
"""
import argparse
import json
import os
import re
import sys
import glob
from datetime import datetime

# ---------------------------------------------------------------------------
# Default values (used when no config file is provided)
# ---------------------------------------------------------------------------

DEFAULT_EMOTIONAL_KEYWORDS = [
    "frustrat", "excit", "breakthrough", "finally", "aha", "damn", "hell",
    "love", "hate", "annoy", "stuck", "confus", "wow", "amazing", "beautiful",
    "ugly", "terrible", "horrible", "incredible", "magic", "magical",
    "inspired", "inspiration", "creative", "creativity", "art", "artist",
    "philosophy", "philosophical", "meaning", "purpose", "vision",
    "dream", "passion", "proud", "disappoint", "surpris", "shock",
    "satisfy", "satisfying", "elegant", "inelegant", "kludge", "hack",
    "eureka", "awesome", "disgust", "delight", "joy", "rage", "anger",
    "happy", "sad", "nervous", "anxious", "worried", "relief", "celebrate",
    "ship", "shipped", "done", "works", "working", "fixed", "broke",
    "painful", "pain", "hard", "easy", "simple", "complicated",
]

DEFAULT_PHILOSOPHICAL_KEYWORDS = [
    "why are we", "what is the point", "the whole idea", "the vision",
    "i want to", "i believe", "the goal is", "the dream", "the mission",
    "this project is", "what i really", "the truth is", "honestly",
    "at the end of the day", "the real question", "fundamentally",
    "the deeper", "meta", "recursive", "self-", "emergent", "emergence",
    "consciousness", "intelligence", "creative coding", "agent",
    "ai should", "ai could", "ai is", "what if", "imagine",
    "i think we should", "let's think about", "bigger picture",
    "the story", "the narrative", "the journey",
    "this is about", "the whole point", "it's not about",
    "we're building", "we are building", "end goal",
]

DEFAULT_REDACT_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{20,}', '[REDACTED_API_KEY]'),
    (r'key["\s:=]+[a-zA-Z0-9]{32,}', '[REDACTED_KEY]'),
    (r'token["\s:=]+[a-zA-Z0-9]{20,}', '[REDACTED_TOKEN]'),
    (r'password["\s:=]+\S+', '[REDACTED_PASSWORD]'),
    (r'[\w.+-]+@[\w.-]+\.\w+', '[REDACTED_EMAIL]'),
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'github_pat_[a-zA-Z0-9_]{82}', '[REDACTED_GITHUB_TOKEN]'),
    (r'AKIA[0-9A-Z]{16}', '[REDACTED_AWS_KEY]'),
]

# Label used for config-provided patterns that don't specify one.
_UNLABELLED_REDACT = '[REDACTED]'


# ---------------------------------------------------------------------------
# Config loading helpers
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load a JSON config file and return the session_extraction section."""
    if not config_path or not os.path.exists(config_path):
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('session_extraction', {})


def resolve_config(args):
    """Build effective keyword lists and redaction patterns from args + config.

    Resolution order:
      1. If --project is given (and no --config), load projects/<name>/project.json
      2. If --config is given, load that file
      3. Fall back to module-level defaults
    """
    config_path = args.config

    if args.project and not config_path:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(repo_root, 'projects', args.project, 'project.json')
        if os.path.exists(candidate):
            config_path = candidate

    cfg = load_config(config_path)

    emotional = cfg.get('emotional_keywords', DEFAULT_EMOTIONAL_KEYWORDS)
    philosophical = cfg.get('philosophical_keywords', DEFAULT_PHILOSOPHICAL_KEYWORDS)

    # Redaction patterns: config may provide raw regex strings or [pattern, label] pairs.
    raw_patterns = cfg.get('redaction_patterns', None)
    if raw_patterns is None:
        redact_patterns = list(DEFAULT_REDACT_PATTERNS)
    else:
        redact_patterns = []
        for entry in raw_patterns:
            if isinstance(entry, list) and len(entry) >= 2:
                redact_patterns.append((entry[0], entry[1]))
            elif isinstance(entry, str):
                redact_patterns.append((entry, _UNLABELLED_REDACT))

    return emotional, philosophical, redact_patterns


# ---------------------------------------------------------------------------
# Text processing helpers
# ---------------------------------------------------------------------------

def redact_text(text, redact_patterns=None):
    if redact_patterns is None:
        redact_patterns = DEFAULT_REDACT_PATTERNS
    if not isinstance(text, str):
        return str(text)
    for pattern, replacement in redact_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def extract_human_text(content):
    """Extract only the human-typed text from user message content.
    Filters out tool_result blocks and file content dumps."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    texts.append(block.get('text', ''))
                # Skip tool_result blocks entirely - those are tool outputs, not human text
                # Skip tool_use blocks - those are agent tool calls
            elif isinstance(block, str):
                texts.append(block)
        return '\n'.join(texts)
    return str(content)


def extract_assistant_text(content):
    """Extract only text blocks from assistant content."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get('type') == 'text':
                    texts.append(block.get('text', ''))
                # Skip tool_use blocks - we just want the narrative text
            elif isinstance(block, str):
                texts.append(block)
        return '\n'.join(texts)
    return str(content)


def is_tool_result_noise(text):
    """Check if a human message is just tool result noise."""
    if not text or not text.strip():
        return True

    stripped = text.strip()

    # Pure file content dumps (start with line numbers)
    if re.match(r'^\s*\d+[→|]', stripped):
        return True

    # Pure diff output
    if stripped.startswith('diff --git') or stripped.startswith('--- a/') or stripped.startswith('+++ b/'):
        return True
    if re.match(r'^\+[^+]', stripped) and len(stripped.split('\n')) > 5:
        return True
    if re.match(r'^-[^-]', stripped) and len(stripped.split('\n')) > 5:
        return True

    # Pure file path listings
    if stripped.startswith('/') and len(stripped.split('\n')) > 5 and all(l.startswith('/') for l in stripped.split('\n')):
        return True

    # Mostly code (over 60% looks like code)
    lines = stripped.split('\n')
    code_lines = 0
    for l in lines:
        if re.match(r'^\s*(import |export |const |let |var |function |class |interface |type |if |for |while |return |}\s*$|{\s*$|\)\s*$|^\s*\d+[→|])', l):
            code_lines += 1
    if len(lines) > 3 and code_lines / len(lines) > 0.6:
        return True

    # Very short file update confirmations
    if re.match(r'^The file .+ has been (updated|created|deleted) successfully\.?$', stripped):
        return True

    # Task notification XML blocks
    if stripped.startswith('<task-notification>'):
        return True
    if '<task-notification>' in stripped and '<task-id>' in stripped:
        return True

    # Subagent completion summaries (auto-generated)
    if re.match(r'^Agent ".+" (completed|failed)', stripped):
        return True

    # Messages that are mostly task-notification content
    if stripped.count('<task-') > 3:
        return True

    # Skill/plugin content dumps (Claude Code plugins injecting instructions)
    if stripped.startswith('Base directory for this skill:') or 'skills/brainstorming' in stripped:
        return True
    if stripped.startswith('# Brainstorming Ideas') or 'HARD-GATE' in stripped:
        return True
    if '<HARD-GATE>' in stripped and len(stripped) > 500:
        return True

    # Very long plan dumps (>2000 chars, mostly formatted plans not dialogue)
    # But keep shorter messages that are plans since they show intent
    if len(stripped) > 3000 and stripped.count('\n') > 30:
        # Check if it's mostly structural content (headers, lists, code blocks)
        structural = stripped.count('\n#') + stripped.count('\n-') + stripped.count('\n```')
        if structural > 15:
            return True

    return False


def truncate(text, max_len=600):
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def is_interesting(text, keywords):
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Session parsing
# ---------------------------------------------------------------------------

def parse_session(filepath):
    session_id = os.path.basename(filepath).replace('.jsonl', '')
    messages = []
    ai_title = None
    session_timestamp = None

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = d.get('type', '')

                if session_timestamp is None and 'timestamp' in d:
                    session_timestamp = d.get('timestamp')

                if msg_type == 'ai-title':
                    ai_title = d.get('aiTitle', d.get('title', d.get('message', '')))

                elif msg_type == 'user':
                    msg = d.get('message', {})
                    content = extract_human_text(msg.get('content', ''))
                    if content and content.strip():
                        messages.append({
                            'type': 'user',
                            'role': 'user',
                            'content': content,
                            'timestamp': d.get('timestamp', ''),
                        })

                elif msg_type == 'assistant':
                    msg = d.get('message', {})
                    content = extract_assistant_text(msg.get('content', ''))
                    if content and content.strip():
                        messages.append({
                            'type': 'assistant',
                            'role': 'assistant',
                            'content': content,
                            'timestamp': d.get('timestamp', ''),
                        })
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return {
            'session_id': session_id,
            'error': str(e),
            'ai_title': ai_title,
            'timestamp': session_timestamp,
        }

    # Filter human messages to only genuine human dialogue
    genuine_human = []
    for m in messages:
        if m['role'] != 'user':
            continue
        text = m['content'].strip()
        # Skip IDE notifications
        if text.startswith('<ide_opened_file>') or text.startswith('<ide_closed_file>'):
            continue
        # Skip pure tool result noise
        if is_tool_result_noise(text):
            continue
        genuine_human.append(m)

    assistant_msgs = [m for m in messages if m['role'] == 'assistant']

    # Generate a fallback title from first substantive human message
    fallback_title = None
    for m in genuine_human:
        text = m['content'].strip()
        if len(text) > 10 and not text.startswith('[Request interrupted'):
            first_line = text.split('\n')[0].strip()
            fallback_title = first_line[:80]
            break

    return {
        'session_id': session_id,
        'ai_title': ai_title,
        'fallback_title': fallback_title,
        'timestamp': session_timestamp,
        'human_messages': genuine_human,
        'assistant_messages': assistant_msgs,
        'total_human': len(genuine_human),
        'total_assistant': len(assistant_msgs),
    }


# ---------------------------------------------------------------------------
# Narrative extraction
# ---------------------------------------------------------------------------

def extract_narrative(session_data, emotional_keywords=None, philosophical_keywords=None,
                      redact_patterns=None):
    if emotional_keywords is None:
        emotional_keywords = DEFAULT_EMOTIONAL_KEYWORDS
    if philosophical_keywords is None:
        philosophical_keywords = DEFAULT_PHILOSOPHICAL_KEYWORDS
    if redact_patterns is None:
        redact_patterns = DEFAULT_REDACT_PATTERNS

    sid = session_data['session_id']
    title = session_data.get('ai_title') or session_data.get('fallback_title') or 'Untitled Session'
    timestamp = session_data.get('timestamp', '')
    human_msgs = session_data.get('human_messages', [])
    assistant_msgs = session_data.get('assistant_messages', [])

    if session_data.get('error'):
        return f"## Session: Error\n**ID**: `{sid}`\n**Error**: {session_data['error']}\n\n---\n\n"

    if not human_msgs and not assistant_msgs:
        return f"## Session: Empty\n**ID**: `{sid}`\n*No messages found.*\n\n---\n\n"

    ts_display = ''
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            ts_display = dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            ts_display = timestamp[:16]

    md = f"## Session: {redact_text(title, redact_patterns)}\n"
    md += f"**ID**: `{sid}`  \n"
    md += f"**Date**: {ts_display}  \n"
    md += f"**Messages**: {len(human_msgs)} human, {len(assistant_msgs)} assistant  \n\n"

    # --- HUMAN INTENT ---
    md += "### Human Intent\n\n"
    first_real = None
    for m in human_msgs:
        text = m['content'].strip()
        if len(text) > 20:
            first_real = text
            break

    if first_real:
        md += f"> {redact_text(truncate(first_real, 500), redact_patterns)}\n\n"

    # --- ALL GENUINE HUMAN MESSAGES ---
    md += "### Human Messages\n\n"
    for i, m in enumerate(human_msgs):
        text = m['content'].strip()
        if not text:
            continue
        redacted = redact_text(text, redact_patterns)
        md += f"**[{i+1}]** {truncate(redacted, 500)}\n\n"

    # --- KEY ASSISTANT MOMENTS ---
    md += "### Key Assistant Responses\n\n"

    interesting_assistant = []
    for idx, m in enumerate(assistant_msgs):
        text = m['content']
        if is_interesting(text, emotional_keywords) or is_interesting(text, philosophical_keywords):
            interesting_assistant.append(idx)

    indices_to_show = set()
    if assistant_msgs:
        indices_to_show.add(0)
    if len(assistant_msgs) > 1:
        indices_to_show.add(len(assistant_msgs) - 1)
    for idx in interesting_assistant[:5]:
        indices_to_show.add(idx)
        if len(indices_to_show) >= 7:
            break

    for idx in sorted(indices_to_show):
        m = assistant_msgs[idx]
        text = redact_text(truncate(m['content'], 500), redact_patterns)
        md += f"**[Assistant #{idx+1}]** {text}\n\n"

    # --- EMOTIONAL MOMENTS ---
    emotional_human = [m for m in human_msgs if is_interesting(m['content'], emotional_keywords)]
    emotional_assistant = [m for m in assistant_msgs if is_interesting(m['content'], emotional_keywords)]

    if emotional_human or emotional_assistant:
        md += "### Emotional Moments\n\n"
        for m in emotional_human[:4]:
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[Human]** {text}\n\n"
        for m in emotional_assistant[:4]:
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[Agent]** {text}\n\n"

    # --- PHILOSOPHICAL MOMENTS ---
    phil_human = [m for m in human_msgs if is_interesting(m['content'], philosophical_keywords)]
    phil_assistant = [m for m in assistant_msgs if is_interesting(m['content'], philosophical_keywords)]

    if phil_human or phil_assistant:
        md += "### Philosophical Moments\n\n"
        for m in phil_human[:4]:
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[Human]** {text}\n\n"
        for m in phil_assistant[:4]:
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[Agent]** {text}\n\n"

    # --- CREATIVE DECISIONS ---
    decision_keywords = [
        "let's call", "named", "rename", "should we", "i think", "what about",
        "how about", "instead of", "better to", "let's use", "let's go with",
        "the name", "naming", "i prefer", "design decision", "architectural",
        "i want", "i don't want", "make it", "this should", "this needs to",
        "the idea is", "concept here", "the approach",
    ]
    decision_msgs = [m for m in human_msgs if is_interesting(m['content'], decision_keywords)]
    if decision_msgs:
        md += "### Creative/Design Decisions\n\n"
        for m in decision_msgs[:5]:
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[Human]** {text}\n\n"

    # --- TECHNICAL BREAKTHROUGHS ---
    breakthrough_keywords = [
        "finally works", "got it working", "this works", "test passes",
        "all tests pass", "build passes", "success", "breakthrough",
        "figured out", "solved", "the fix", "working now",
        "it's alive", "that did it", "nailed it", "perfect",
    ]
    tech_msgs = [m for m in human_msgs + assistant_msgs if is_interesting(m['content'], breakthrough_keywords)]
    if tech_msgs:
        md += "### Technical Breakthroughs\n\n"
        for m in tech_msgs[:4]:
            role = "Human" if m['role'] == 'user' else "Agent"
            text = redact_text(truncate(m['content'], 400), redact_patterns)
            md += f"**[{role}]** {text}\n\n"

    md += "---\n\n"
    return md


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract narrative material from Claude Code JSONL session files.")
    parser.add_argument(
        "--sessions-dir",
        default=os.path.expanduser("~/.claude/projects/"),
        help="Directory containing .jsonl session files (default: ~/.claude/projects/)")
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown file (default: <repo-root>/data/raw-sessions.md)")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON config file with session_extraction settings")
    parser.add_argument(
        "--project",
        default=None,
        help="Project name; loads projects/<name>/project.json for config")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    sessions_dir = os.path.expanduser(args.sessions_dir)
    if not os.path.isdir(sessions_dir):
        print(f"Error: sessions directory not found: {sessions_dir}", file=sys.stderr)
        sys.exit(1)

    # Resolve output path
    output_file = args.output
    if output_file is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_file = os.path.join(repo_root, "data", "raw-sessions.md")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Resolve config (keywords + redaction patterns)
    emotional_kw, philosophical_kw, redact_pat = resolve_config(args)

    files = sorted(glob.glob(os.path.join(sessions_dir, "*.jsonl")))
    print(f"Found {len(files)} session files in {sessions_dir}")

    sessions = []
    for f in files:
        session_id = os.path.basename(f).replace('.jsonl', '')
        print(f"  Parsing {session_id}...")
        data = parse_session(f)
        sessions.append(data)

    # Sort by timestamp
    sessions.sort(key=lambda s: s.get('timestamp') or '')

    # Derive project name for the header (from --project arg or cwd)
    project_name = args.project or os.path.basename(os.path.abspath("."))

    output_parts = []
    output_parts.append(f"# {project_name.title()} Session Narratives\n\n")
    output_parts.append(f"Extracted from {len(files)} Claude Code session logs.\n")
    output_parts.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    output_parts.append(f"Note: Tool-result noise (file contents, diffs, code dumps) filtered out. ")
    output_parts.append("Only genuine human dialogue and agent narrative text included.\n\n")
    output_parts.append("---\n\n")

    for data in sessions:
        print(f"  Extracting narrative for {data['session_id']} ({data['total_human']} human msgs)...")
        narrative = extract_narrative(
            data,
            emotional_keywords=emotional_kw,
            philosophical_keywords=philosophical_kw,
            redact_patterns=redact_pat,
        )
        output_parts.append(narrative)

    full_output = ''.join(output_parts)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(full_output)

    print(f"\nDone! Written to {output_file}")
    print(f"Total size: {len(full_output):,} characters")

    total_human = sum(s.get('total_human', 0) for s in sessions)
    total_assistant = sum(s.get('total_assistant', 0) for s in sessions)
    sessions_with_content = sum(1 for s in sessions if s.get('total_human', 0) > 0)
    print(f"Sessions with human dialogue: {sessions_with_content}/{len(sessions)}")
    print(f"Total genuine human messages: {total_human}")
    print(f"Total assistant messages: {total_assistant}")


if __name__ == '__main__':
    main()
