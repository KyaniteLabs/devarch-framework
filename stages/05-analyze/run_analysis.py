#!/usr/bin/env python3
"""Stage 05-Analyze: Run Analysis Vectors"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Paths
DB_PATH = Path("/Users/simongonzalezdecruz/workspaces/devarch-framework/stages/03-build/output/archaeology.db")
SIGNALS_PATH = Path("/Users/simongonzalezdecruz/workspaces/devarch-framework/stages/04-detect/output/detected-signals.json")
OUTPUT_DIR = Path("/Users/simongonzalezdecruz/workspaces/devarch-framework/stages/05-analyze/output")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_commits():
    """Load all commits from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT hash, author, date, message
        FROM commits
        ORDER BY date
    """)

    commits = []
    for row in cursor.fetchall():
        hash_val, author, date_str, message = row
        date_obj = datetime.strptime(date_str.split(' -')[0], '%Y-%m-%d %H:%M:%S')
        commits.append({
            'hash': hash_val,
            'author': author,
            'date': date_obj,
            'message': message
        })

    conn.close()
    return commits

def load_signals():
    """Load detected signals"""
    with open(SIGNALS_PATH, 'r') as f:
        return json.load(f)

def analyze_sdlc_gaps(commits, signals):
    """Vector 1: SDLC Gap Finder - Identify missing SDLC practices"""

    findings = []

    # Check for CI/CD evidence
    ci_cd_commits = [c for c in commits if any(term in c['message'].lower() for term in ['ci', 'github action', 'workflow', '.yml', '.yaml', 'pipeline', 'deploy'])]
    if ci_cd_commits:
        findings.append({
            'type': 'CI/CD Present',
            'description': f'Found {len(ci_cd_commits)} commits related to CI/CD infrastructure',
            'evidence': [c['message'] for c in ci_cd_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'CI/CD Missing',
            'description': 'No CI/CD infrastructure detected in commit messages',
            'evidence': [],
            'confidence': 'medium'
        })

    # Check for testing evidence
    test_commits = [c for c in commits if any(term in c['message'].lower() for term in ['test:', 'testing', 'test coverage', 'integration test', 'unit test', 'spec'])]
    if len(test_commits) >= 5:
        findings.append({
            'type': 'Testing Present',
            'description': f'Found {len(test_commits)} test-related commits',
            'evidence': [c['message'] for c in test_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'Testing Limited',
            'description': f'Only {len(test_commits)} test-related commits found',
            'evidence': [c['message'] for c in test_commits] if test_commits else [],
            'confidence': 'medium'
        })

    # Check for code review evidence
    review_commits = [c for c in commits if any(term in c['message'].lower() for term in ['review', 'pr #', 'pull request', 'merge', 'merge pull request'])]
    if len(review_commits) >= 3:
        findings.append({
            'type': 'Code Review Present',
            'description': f'Found {len(review_commits)} commits indicating code review/PR activity',
            'evidence': [c['message'] for c in review_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'Code Review Limited',
            'description': 'Limited evidence of code review processes',
            'evidence': [c['message'] for c in review_commits] if review_commits else [],
            'confidence': 'medium'
        })

    # Check for documentation
    doc_commits = [c for c in commits if any(term in c['message'].lower() for term in ['docs:', 'readme', 'documentation', 'doc:', 'updating docs'])]
    if len(doc_commits) >= 3:
        findings.append({
            'type': 'Documentation Present',
            'description': f'Found {len(doc_commits)} documentation-related commits',
            'evidence': [c['message'] for c in doc_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'Documentation Limited',
            'description': 'Limited documentation activity detected',
            'evidence': [c['message'] for c in doc_commits] if doc_commits else [],
            'confidence': 'medium'
        })

    # Check for security considerations
    security_commits = [c for c in commits if any(term in c['message'].lower() for term in ['security', 'vulnerability', 'auth', 'permission', 'secure'])]
    if security_commits:
        findings.append({
            'type': 'Security Considered',
            'description': f'Found {len(security_commits)} security-related commits',
            'evidence': [c['message'] for c in security_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'Security Not Explicit',
            'description': 'No explicit security considerations detected',
            'evidence': [],
            'confidence': 'low'
        })

    # Check commit message quality (conventional commits)
    conventional_pattern = re.compile(r'^(feat|fix|docs|style|refactor|test|chore|perf)(\(.+\))?\s*:\s+.+')
    conventional_commits = [c for c in commits if conventional_pattern.match(c['message'])]
    cc_percentage = len(conventional_commits) / len(commits) * 100

    if cc_percentage >= 70:
        findings.append({
            'type': 'Commit Hygiene Good',
            'description': f'{cc_percentage:.1f}% of commits follow conventional commit format',
            'evidence': [c['message'] for c in conventional_commits[:3]],
            'confidence': 'high'
        })
    else:
        findings.append({
            'type': 'Commit Hygiene Fair',
            'description': f'Only {cc_percentage:.1f}% of commits follow conventional commit format',
            'evidence': [c['message'] for c in conventional_commits[:3]],
            'confidence': 'medium'
        })

    return {
        'vector_name': 'SDLC Gap Finder',
        'findings': findings,
        'summary': {
            'total_findings': len(findings),
            'by_type': {f['type']: 1 for f in findings}
        }
    }

def analyze_ml_patterns(commits, signals):
    """Vector 2: ML Pattern Mapper - Map codebase patterns to ML concepts"""

    findings = []

    # Analyze project context from commit messages
    commit_texts = [c['message'].lower() for c in commits]
    all_text = ' '.join(commit_texts)

    # Detect ML-related patterns
    ml_keywords = {
        'training_data': ['recipe data', 'ingredient data', 'training data', 'dataset'],
        'inference': ['inference', 'generation', 'predict', 'recommend'],
        'model': ['model', 'embedding', 'vector', 'classifier'],
        'feature_extraction': ['extract', 'feature', 'profile', 'attribute'],
        'preprocessing': ['clean', 'normalize', 'standardize', 'parse'],
        'evaluation': ['test', 'validate', 'evaluate', 'accuracy', 'benchmark'],
        'deployment': ['deploy', 'production', 'serve', 'api', 'mcp']
    }

    detected_patterns = {}
    for concept, keywords in ml_keywords.items():
        matches = [c for c in commits if any(kw in c['message'].lower() for kw in keywords)]
        if matches:
            detected_patterns[concept] = len(matches)
            findings.append({
                'type': f'ML Pattern: {concept}',
                'description': f'Detected {len(matches)} commits related to {concept}',
                'evidence': [c['message'] for c in matches[:3]],
                'confidence': 'high'
            })

    # Check for architectural patterns
    architecture_patterns = {
        'data_pipeline': ['cache', 'database', 'sqlite', 'storage'],
        'api_design': ['api', 'endpoint', 'server', 'mcp', 'tool'],
        'mcp_server': ['mcp', 'tool', 'server', 'claude'],
        'data_modeling': ['type definition', 'interface', 'schema', 'compound']
    }

    for pattern, keywords in architecture_patterns.items():
        matches = [c for c in commits if any(kw in c['message'].lower() for kw in keywords)]
        if matches:
            findings.append({
                'type': f'Architecture: {pattern}',
                'description': f'Detected {len(matches)} commits implementing {pattern}',
                'evidence': [c['message'] for c in matches[:3]],
                'confidence': 'high'
            })

    if not findings:
        findings.append({
            'type': 'ML Patterns Not Detected',
            'description': 'No clear ML patterns detected in commit messages',
            'evidence': [],
            'confidence': 'low'
        })

    return {
        'vector_name': 'ML Pattern Mapper',
        'findings': findings,
        'summary': {
            'total_findings': len(findings),
            'by_type': {f['type']: 1 for f in findings}
        }
    }

def analyze_formal_terms(commits, signals):
    """Vector 3: Formal Terms Mapper - Map informal vocabulary to formal engineering terms"""

    findings = []

    # Domain-specific terms and their formal equivalents
    term_mappings = {
        'recipe': 'structured data model',
        'ingredient': 'data entity',
        'dish': 'domain entity',
        'flavor': 'sensory attribute',
        'substitution': 'algorithmic transformation',
        'research cache': 'data persistence layer',
        'MCP': 'Model Context Protocol server',
        'fuzzy matching': 'approximate string matching algorithm',
        'transliteration': 'text normalization',
        'chemistry-aware': 'domain-specific logic',
        'regional availability': 'geospatial data'
    }

    # Detect usage of informal terms
    for informal, formal in term_mappings.items():
        matches = [c for c in commits if informal.lower() in c['message'].lower()]
        if matches:
            findings.append({
                'type': 'Terminology Mapping',
                'description': f'"{informal}" maps to formal term: "{formal}"',
                'evidence': [c['message'] for c in matches[:3]],
                'confidence': 'high',
                'mapping': {
                    'informal': informal,
                    'formal': formal,
                    'occurrences': len(matches)
                }
            })

    # Detect commit message conventions
    conventional_commits = [c for c in commits if re.match(r'^(feat|fix|docs|test|chore|refactor):', c['message'])]
    if conventional_commits:
        findings.append({
            'type': 'Formal Convention',
            'description': 'Project uses Conventional Commits specification',
            'evidence': [c['message'] for c in conventional_commits[:3]],
            'confidence': 'high',
            'mapping': {
                'informal': 'various commit message styles',
                'formal': 'Conventional Commits (ConCommits)',
                'occurrences': len(conventional_commits)
            }
        })

    # Detect architectural patterns
    if any('mcp' in c['message'].lower() for c in commits):
        findings.append({
            'type': 'Formal Convention',
            'description': 'Project implements MCP (Model Context Protocol) architecture',
            'evidence': [c['message'] for c in commits if 'mcp' in c['message'].lower()][:3],
            'confidence': 'high',
            'mapping': {
                'informal': 'server/tool integration',
                'formal': 'Model Context Protocol (MCP) server',
                'occurrences': len([c for c in commits if 'mcp' in c['message'].lower()])
            }
        })

    return {
        'vector_name': 'Formal Terms Mapper',
        'findings': findings,
        'summary': {
            'total_findings': len(findings),
            'by_type': {f['type']: 1 for f in findings}
        }
    }

def analyze_source_archaeology(commits, signals):
    """Vector 4: Source Archaeologist - Quality trajectory and development patterns"""

    findings = []

    # Analyze commit type distribution over time
    commit_types = defaultdict(list)
    for commit in commits:
        msg = commit['message'].lower()
        if msg.startswith('feat:'):
            commit_types['feat'].append(commit)
        elif msg.startswith('fix:'):
            commit_types['fix'].append(commit)
        elif msg.startswith('test:'):
            commit_types['test'].append(commit)
        elif msg.startswith('docs:'):
            commit_types['docs'].append(commit)
        elif msg.startswith('refactor:'):
            commit_types['refactor'].append(commit)
        elif msg.startswith('chore:'):
            commit_types['chore'].append(commit)
        else:
            commit_types['other'].append(commit)

    # Feature development health
    feat_ratio = len(commit_types['feat']) / len(commits) * 100
    if feat_ratio >= 40:
        findings.append({
            'type': 'Feature Development',
            'description': f'Healthy feature development: {feat_ratio:.1f}% feature commits',
            'evidence': [c['message'] for c in commit_types['feat'][:3]],
            'confidence': 'high'
        })

    # Bug fix patterns
    fix_ratio = len(commit_types['fix']) / len(commits) * 100
    if fix_ratio > 20:
        findings.append({
            'type': 'Bug Fix Load',
            'description': f'High bug fix activity: {fix_ratio:.1f}% fix commits may indicate quality issues',
            'evidence': [c['message'] for c in commit_types['fix'][:3]],
            'confidence': 'medium'
        })
    elif fix_ratio > 0:
        findings.append({
            'type': 'Bug Fix Pattern',
            'description': f'Moderate bug fix activity: {fix_ratio:.1f}% fix commits',
            'evidence': [c['message'] for c in commit_types['fix'][:3]],
            'confidence': 'high'
        })

    # Testing practices
    test_ratio = len(commit_types['test']) / len(commits) * 100
    if test_ratio >= 10:
        findings.append({
            'type': 'Testing Culture',
            'description': f'Strong testing culture: {test_ratio:.1f}% test commits',
            'evidence': [c['message'] for c in commit_types['test'][:3]],
            'confidence': 'high'
        })
    elif test_ratio > 0:
        findings.append({
            'type': 'Testing Present',
            'description': f'Testing present but limited: {test_ratio:.1f}% test commits',
            'evidence': [c['message'] for c in commit_types['test'][:3]],
            'confidence': 'medium'
        })

    # Documentation practices
    docs_ratio = len(commit_types['docs']) / len(commits) * 100
    if docs_ratio >= 5:
        findings.append({
            'type': 'Documentation Practice',
            'description': f'Good documentation practice: {docs_ratio:.1f}% documentation commits',
            'evidence': [c['message'] for c in commit_types['docs'][:3]],
            'confidence': 'high'
        })

    # Refactoring activity
    refactor_ratio = len(commit_types['refactor']) / len(commits) * 100
    if refactor_ratio >= 5:
        findings.append({
            'type': 'Code Maintenance',
            'description': f'Active code maintenance: {refactor_ratio:.1f}% refactor commits',
            'evidence': [c['message'] for c in commit_types['refactor'][:3]],
            'confidence': 'high'
        })

    # Commit message quality
    conventional_pattern = re.compile(r'^(feat|fix|docs|style|refactor|test|chore|perf)(\(.+\))?\s*:\s*.+')
    conventional_count = sum(1 for c in commits if conventional_pattern.match(c['message']))
    quality_score = conventional_count / len(commits) * 100

    if quality_score >= 80:
        findings.append({
            'type': 'Commit Hygiene',
            'description': f'Excellent commit hygiene: {quality_score:.1f}% follow conventions',
            'evidence': [],
            'confidence': 'high'
        })
    elif quality_score >= 50:
        findings.append({
            'type': 'Commit Hygiene',
            'description': f'Good commit hygiene: {quality_score:.1f}% follow conventions',
            'evidence': [],
            'confidence': 'medium'
        })

    # Development velocity
    if len(commits) > 0:
        first_date = commits[0]['date']
        last_date = commits[-1]['date']
        days_active = (last_date.date() - first_date.date()).days + 1
        velocity = len(commits) / days_active if days_active > 0 else 0

        if velocity >= 10:
            findings.append({
                'type': 'Development Velocity',
                'description': f'High velocity: {velocity:.1f} commits/day over {days_active} days',
                'evidence': [],
                'confidence': 'high'
            })
        elif velocity >= 5:
            findings.append({
                'type': 'Development Velocity',
                'description': f'Moderate velocity: {velocity:.1f} commits/day over {days_active} days',
                'evidence': [],
                'confidence': 'high'
            })

    # Check for signal patterns from detected signals
    if signals:
        signal_types = [s['type'] for s in signals.get('signals', [])]
        if 'gap' in signal_types:
            gap_count = signal_types.count('gap')
            findings.append({
                'type': 'Development Continuity',
                'description': f'Found {gap_count} gap(s) in development activity',
                'evidence': [],
                'confidence': 'high'
            })

    return {
        'vector_name': 'Source Archaeologist',
        'findings': findings,
        'summary': {
            'total_findings': len(findings),
            'by_type': {f['type']: 1 for f in findings}
        }
    }

def generate_markdown_report(analysis_data, vector_name):
    """Generate markdown report from JSON analysis"""

    md_lines = [
        f"# {vector_name}\n",
        f"**Total Findings:** {analysis_data['summary']['total_findings']}\n",
        "---\n"
    ]

    for finding in analysis_data['findings']:
        md_lines.append(f"## {finding['type']}\n")
        md_lines.append(f"**Description:** {finding['description']}\n")
        md_lines.append(f"**Confidence:** {finding['confidence']}\n")

        if finding['evidence']:
            md_lines.append("**Evidence:**\n")
            for evidence in finding['evidence']:
                md_lines.append(f"- {evidence}\n")

        md_lines.append("\n")

    return ''.join(md_lines)

if __name__ == '__main__':
    commits = load_commits()
    signals = load_signals()

    print(f"Loaded {len(commits)} commits")
    print(f"Loaded signals with {signals['summary']['total_signals']} total signals\n")

    # Run all analysis vectors
    vectors = [
        ('analysis-sdlc-gap-finder', analyze_sdlc_gaps),
        ('analysis-ml-pattern-mapper', analyze_ml_patterns),
        ('analysis-formal-terms-mapper', analyze_formal_terms),
        ('analysis-source-archaeologist', analyze_source_archaeology)
    ]

    for vector_name, analyze_func in vectors:
        print(f"Running {vector_name}...")

        result = analyze_func(commits, signals)

        # Write JSON output
        json_path = OUTPUT_DIR / f"{vector_name}.json"
        with open(json_path, 'w') as f:
            json.dump(result, f, indent=2)

        # Write Markdown output
        md_path = OUTPUT_DIR / f"{vector_name}.md"
        with open(md_path, 'w') as f:
            f.write(generate_markdown_report(result, vector_name))

        print(f"  ✓ {result['summary']['total_findings']} findings")

    print(f"\n✓ Stage 05-Analyze completed")
    print(f"  Outputs written to: {OUTPUT_DIR}")
