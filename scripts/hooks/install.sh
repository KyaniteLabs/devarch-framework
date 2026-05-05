#!/usr/bin/env bash
#
# Install git hooks for dev-archaeology
# Symlinks hooks from scripts/hooks/ to .git/hooks/
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_SRC="$SCRIPT_DIR"
HOOKS_DST="$REPO_ROOT/.git/hooks"

echo "📦 Installing git hooks for dev-archaeology..."
echo ""

# Ensure hooks directory exists
mkdir -p "$HOOKS_DST"

# List of hooks to install
HOOKS=("pre-commit" "pre-push")

for hook in "${HOOKS[@]}"; do
    src="$HOOKS_SRC/$hook"
    dst="$HOOKS_DST/$hook"

    # Remove existing hook if present (idempotent)
    if [ -L "$dst" ]; then
        echo "🔄 Removing existing symlink: $hook"
        rm "$dst"
    elif [ -f "$dst" ]; then
        echo "⚠️  Backing up existing hook: $hook → $hook.bak"
        mv "$dst" "$dst.bak"
    fi

    # Create symlink
    ln -s "$src" "$dst"
    echo "✓ Installed: $hook"
done

echo ""
echo "✅ Git hooks installed successfully"
echo ""
echo "Active hooks:"
echo "  • pre-commit  – Era scanner + framework sync reminder"
echo "  • pre-push    – Audit + parity check (blocks on failure)"
