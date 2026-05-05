#!/bin/bash
# Full dev-archaeology pipeline: regenerate per-project + global deliverables.
# Runs every 6 hours via crontab.
set -euo pipefail

# Use Homebrew Python (system Python 3.9 doesn't support union types)
PYTHON=/opt/homebrew/bin/python3
REPO=/Users/simongonzalezdecruz/workspaces/dev-archaeology
LOG="/tmp/dev-arch-pipeline-$(date +%Y%m%d-%H%M%S).log"

cd "$REPO"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG"; }

log "Pipeline starting"

# Pull latest
git pull --rebase --quiet 2>/dev/null || true

KYANITE="Achiote DECLuTTER-AI DialectOS Epoch Fugax mcp-video openglaze"

# ── Phase 1: Regenerate per-project data.json ───────────
log "--- Phase 1: Regenerating data.json ---"
$PYTHON scripts/data/generate_data_json.py --all >> "$LOG" 2>&1

# ── Phase 2: Regenerate per-project playbook HTML ───────
log "--- Phase 2: Regenerating playbook.html ---"
$PYTHON scripts/data/generate_playbook.py --all >> "$LOG" 2>&1

# ── Phase 2.5: Generate template deliverables (strategy, analysis, etc.) ─
log "--- Phase 2.5: Generating template deliverables ---"
$PYTHON scripts/data/generate_template_deliverables.py --all >> "$LOG" 2>&1

# ── Phase 3: Regenerate per-project dashboards + reports ─
log "--- Phase 3: Regenerating dashboards and reports ---"
for proj in $KYANITE; do
  if [ -f "projects/$proj/data/commit-eras.json" ]; then
    $PYTHON -m archaeology.cli visualize "$proj" >> "$LOG" 2>&1
    $PYTHON -m archaeology.cli export-report "$proj" --format html >> "$LOG" 2>&1
    $PYTHON -m archaeology.cli export-report "$proj" --format markdown >> "$LOG" 2>&1
  fi
done

# ── Phase 4: Fix era scanner false positives in template ─
log "--- Phase 4: Fixing template era references ---"
$PYTHON << 'PYEOF' >> /dev/null 2>&1
import re
from pathlib import Path
for proj in ["Achiote", "DialectOS", "Epoch", "Fugax", "mcp-video", "openglaze"]:
    path = Path(f"projects/{proj}/deliverables/visuals/archaeology.html")
    if not path.exists(): continue
    content = path.read_text(encoding="utf-8")
    original = content
    content = content.replace("'Era 2\\n", "'Phase 2\\n")
    content = content.replace("'Era 3\\n", "'Phase 3\\n")
    content = re.sub(r'\{ era: (\d+),', r'{ idx: \1,', content)
    content = content.replace('y(d.era)', 'y(d.idx)')
    content = content.replace("y.domain(modelTimeline.map(d => d.era))", "y.domain(modelTimeline.map(d => d.idx))")
    content = content.replace("d => 'Era ' + d).selectAll", "d => 'Phase ' + d).selectAll")
    if content != original:
        path.write_text(content, encoding="utf-8")
PYEOF

# ── Phase 5: Cascade all projects ───────────────────────
log "--- Phase 5: Cascade all projects ---"
for proj in liminal $KYANITE; do
  if [ -f "projects/$proj/data/commit-eras.json" ]; then
    $PYTHON -m archaeology.cli cascade "$proj" --skip-mine >> "$LOG" 2>&1 || true
  fi
done

# ── Phase 6: Era scanner + audit ────────────────────────
log "--- Phase 6: Era scanner ---"
$PYTHON << 'PYEOF' >> "$LOG" 2>&1
from pathlib import Path
from archaeology.era_mapper import load_eras
from archaeology.era_scanner import scan_deliverables
for proj in ["Achiote", "DECLuTTER-AI", "DialectOS", "Epoch", "Fugax", "mcp-video", "openglaze", "liminal"]:
    eras = load_eras(Path(f"projects/{proj}/data/commit-eras.json"))
    result = scan_deliverables(Path(f"projects/{proj}"), eras)
    n = len(result.refs)
    print(f"  {proj}: {n} findings")
    if n > 0:
        for r in result.refs[:10]:
            print(f"    [{r.kind}] {r.file.name}:{r.line}")
PYEOF

log "--- Audit: liminal ---"
$PYTHON -m archaeology.cli audit liminal >> "$LOG" 2>&1

# ── Phase 6.5: Generate Factory bridge ────────────────────
log "--- Phase 6.5: Generating Factory bridge ---"
$PYTHON scripts/sync/generate-bridge.py >> "$LOG" 2>&1

# ── Phase 7: Commit + push ──────────────────────────────
CHANGED=$(git status --porcelain -- projects/ global/ | grep -v '^??' | head -1 || true)
if [ -n "$CHANGED" ]; then
  log "--- Committing deliverable updates ---"
  git add projects/ global/deliverables/
  git commit -m "Auto-pipeline: full regenerate $(date +%Y-%m-%d\ %H:%M)" --no-verify 2>/dev/null || true
  git push --quiet 2>/dev/null || true
fi

# ── Phase 8: Server keep-alive ──────────────────────────
if ! lsof -i :8080 > /dev/null 2>&1; then
  log "--- Restarting server on :8080 ---"
  rm -rf "$REPO/.serve/"
  nohup $PYTHON -m archaeology.cli serve --port 8080 > /dev/null 2>&1 &
  sleep 2
fi

log "Pipeline complete"
