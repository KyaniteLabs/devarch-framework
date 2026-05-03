#!/bin/bash
# Install git hooks by symlinking them into .git/hooks/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$SCRIPT_DIR"
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks..."

# Create symlinks for each hook
for hook in pre-commit pre-push; do
    if [ -f "$HOOKS_DIR/$hook" ]; then
        chmod +x "$HOOKS_DIR/$hook"
        ln -sf "$HOOKS_DIR/$hook" "$GIT_HOOKS_DIR/$hook"
        echo "✓ Linked $hook"
    else
        echo "⚠ Hook $hook not found, skipping"
    fi
done

echo "Git hooks installed successfully"
