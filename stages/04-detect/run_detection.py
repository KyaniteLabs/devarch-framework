#!/usr/bin/env python3
"""Stage 04-Detect: Signal Detection Pipeline"""

import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Database path
DB_PATH = Path("/Users/simongonzalezdecruz/workspaces/devarch-framework/stages/03-build/output/archaeology.db")
OUTPUT_PATH = Path("/Users/simongonzalezdecruz/workspaces/devarch-framework/stages/04-detect/output/detected-signals.json")

# Ensure output directory exists
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

def analyze_commits():
    """Run all 5 signal detection heuristics"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all commits with dates
    cursor.execute("""
        SELECT hash, author, date, message
        FROM commits
        ORDER BY date
    """)

    commits = []
    for row in cursor.fetchall():
        hash_val, author, date_str, message = row
        # Parse date, handle timezone
        date_obj = datetime.strptime(date_str.split(' -')[0], '%Y-%m-%d %H:%M:%S')
        commits.append({
            'hash': hash_val,
            'author': author,
            'date': date_obj,
            'message': message,
            'day': date_obj.date()
        })

    if not commits:
        print("No commits found!")
        return None

    # Calculate basic stats
    total_commits = len(commits)
    authors = set(c['author'] for c in commits)
    first_commit = commits[0]['date']
    last_commit = commits[-1]['date']
    date_range = f"{first_commit.strftime('%b %d')} - {last_commit.strftime('%b %d, %Y')}"

    # Group by day
    daily_commits = defaultdict(int)
    daily_authors = defaultdict(set)
    for commit in commits:
        day = commit['day']
        daily_commits[day] += 1
        daily_authors[day].add(commit['author'])

    active_days = len(daily_commits)
    span_days = (last_commit.date() - first_commit.date()).days + 1

    signals = []

    # 1. GAP DETECTION: Find periods > 2 days with no commits
    all_days = [first_commit.date() + timedelta(days=i) for i in range(span_days)]
    gap_days = [day for day in all_days if day not in daily_commits]

    # Find consecutive gaps
    if gap_days:
        current_gap_start = gap_days[0]
        current_gap_length = 1

        for i in range(1, len(gap_days)):
            if gap_days[i] == gap_days[i-1] + timedelta(days=1):
                current_gap_length += 1
            else:
                if current_gap_length >= 2:
                    signals.append({
                        'type': 'gap',
                        'date': current_gap_start.isoformat(),
                        'value': current_gap_length,
                        'metadata': {
                            'end_date': (current_gap_start + timedelta(days=current_gap_length - 1)).isoformat(),
                            'description': f"{current_gap_length}-day gap with no commits"
                        }
                    })
                current_gap_start = gap_days[i]
                current_gap_length = 1

        # Don't forget the last gap
        if current_gap_length >= 2:
            signals.append({
                'type': 'gap',
                'date': current_gap_start.isoformat(),
                'value': current_gap_length,
                'metadata': {
                    'end_date': (current_gap_start + timedelta(days=current_gap_length - 1)).isoformat(),
                    'description': f"{current_gap_length}-day gap with no commits"
                }
            })

    # 2. VELOCITY SHIFT DETECTION: Find significant changes in commit frequency
    if len(daily_commits) >= 2:
        velocities = [(day, daily_commits[day]) for day in sorted(daily_commits.keys())]

        for i in range(1, len(velocities)):
            prev_day, prev_count = velocities[i-1]
            curr_day, curr_count = velocities[i]

            # If velocity changed by more than 50% and at least 5 commits
            if prev_count > 0:
                change_pct = abs(curr_count - prev_count) / prev_count
                if change_pct > 0.5 and abs(curr_count - prev_count) >= 5:
                    signals.append({
                        'type': 'velocity_shift',
                        'date': curr_day.isoformat(),
                        'value': curr_count,
                        'metadata': {
                            'previous_velocity': prev_count,
                            'change_percent': round(change_pct * 100, 1),
                            'change_type': 'increase' if curr_count > prev_count else 'decrease',
                            'description': f"Velocity {('increased' if curr_count > prev_count else 'decreased')} from {prev_count} to {curr_count} commits"
                        }
                    })

    # 3. AUTHOR CHANGE DETECTION: Find commits from non-primary authors
    author_counts = defaultdict(int)
    for commit in commits:
        author_counts[commit['author']] += 1

    primary_author = max(author_counts, key=author_counts.get)

    for commit in commits:
        if commit['author'] != primary_author:
            signals.append({
                'type': 'author_change',
                'date': commit['day'].isoformat(),
                'value': commit['author'],
                'metadata': {
                    'commit_hash': commit['hash'],
                    'message': commit['message'][:100],
                    'description': f"Commit by {commit['author']} (non-primary author)"
                }
            })

    # 4. SCOPE CHANGE DETECTION: Find significant changes in commit patterns
    # We'll detect this by looking at clusters of similar commit types
    commit_type_patterns = {
        'feat': 0,
        'fix': 0,
        'docs': 0,
        'test': 0,
        'refactor': 0,
        'chore': 0,
        'other': 0
    }

    for commit in commits:
        msg = commit['message'].lower()
        if msg.startswith('feat:'):
            commit_type_patterns['feat'] += 1
        elif msg.startswith('fix:'):
            commit_type_patterns['fix'] += 1
        elif msg.startswith('docs:'):
            commit_type_patterns['docs'] += 1
        elif msg.startswith('test:'):
            commit_type_patterns['test'] += 1
        elif msg.startswith('refactor:'):
            commit_type_patterns['refactor'] += 1
        elif msg.startswith('chore:'):
            commit_type_patterns['chore'] += 1
        else:
            commit_type_patterns['other'] += 1

    # Detect clusters of activity by type
    for commit_type, count in commit_type_patterns.items():
        if count >= 5:  # Significant cluster threshold
            signals.append({
                'type': 'scope_change',
                'date': first_commit.date().isoformat(),
                'value': commit_type,
                'metadata': {
                    'count': count,
                    'description': f"Cluster of {count} {commit_type} commits detected"
                }
            })

    # 5. SUPPLEMENTARY CORRELATION (placeholder - no supplementary data in this project)
    # This would correlate with external data if available

    # Build clusters from signals
    clusters = []
    for signal_type in ['gap', 'velocity_shift', 'author_change', 'scope_change']:
        type_signals = [s for s in signals if s['type'] == signal_type]
        if type_signals:
            clusters.append({
                'type': signal_type,
                'count': len(type_signals),
                'description': f"{len(type_signals)} {signal_type.replace('_', ' ')} event(s)"
            })

    # Calculate summary
    summary = {
        'total_signals': len(signals),
        'by_type': {}
    }

    for signal in signals:
        signal_type = signal['type']
        summary['by_type'][signal_type] = summary['by_type'].get(signal_type, 0) + 1

    # Build output
    output = {
        'project': 'Achiote',
        'total_commits': total_commits,
        'active_days': active_days,
        'span_days': span_days,
        'date_range': date_range,
        'signals': signals,
        'clusters': clusters,
        'daily_breakdown': {day.isoformat(): count for day, count in sorted(daily_commits.items())},
        'summary': summary
    }

    conn.close()

    return output

if __name__ == '__main__':
    result = analyze_commits()

    if result:
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✓ Stage 04-Detect completed")
        print(f"  Total commits: {result['total_commits']}")
        print(f"  Active days: {result['active_days']}")
        print(f"  Signals detected: {result['summary']['total_signals']}")
        print(f"  Output written to: {OUTPUT_PATH}")
