#!/usr/bin/env bash
# Where the project stands, in one screen:  tools/status.sh
#
# Read-only. Shows the branch and what is not pushed, the working tree (code changes apart from the
# docs/ export, which the vault's post-commit hook rewrites and never commits), the version, how
# current the docs/ export is, waiting mailbox messages and whether the graphify graph is stale.
set -uo pipefail
cd "$(dirname "$0")/.."

echo "== git"
echo "branch: $(git branch --show-current)"
upstream=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || true)
if [ -n "$upstream" ]; then
    echo "not pushed to $upstream: $(git rev-list --count "$upstream"..HEAD) commit(s)"
else
    echo "no upstream branch: nothing of this branch is pushed"
fi
code=$(git status --short -- . ':(exclude)docs' | grep -v '^?? \.pi/$' || true)
docs=$(git status --short -- docs | wc -l)
if [ -n "$code" ]; then echo "uncommitted (code and agent files):"; echo "$code" | sed 's/^/  /'; else echo "no uncommitted code or agent files"; fi
echo "docs/ export: $docs path(s) changed by the vault sync, not committed (the maintainer commits docs/ by hand; never stage them in a code commit)"
echo "recent:"; git log --oneline -5 | sed 's/^/  /'

echo
echo "== version"
if [ -f pyproject.toml ]; then
    grep -m1 '^version' pyproject.toml || echo "pyproject.toml has no static version"
    grep -rm1 '__version__' src/tess_shell/__init__.py 2>/dev/null || true
else
    echo "no pyproject.toml yet (M0 task T1 writes it)"
fi

echo
echo "== docs export"
if [ -f docs/.sync.json ]; then
    python3 -I - <<'PY'
import json
d = json.load(open("docs/.sync.json"))
print(f"vault commit {d['vault_commit'][:8]} ({d['vault_subject']}), exported {d['exported_at']}")
PY
else
    echo "docs/.sync.json is missing"
fi
vault="$HOME/Projects/Obsidian/Tesserae Shell"
if [ -d "$vault/.git" ]; then
    echo "vault HEAD: $(git -C "$vault" log -1 --format='%h %s')"
fi

echo
echo "== mailbox"
if [ -f "$HOME/.claude/mailbox/cli.py" ]; then
    echo "messages waiting: $(python3 -I "$HOME/.claude/mailbox/cli.py" pending 2>/dev/null || echo 'not configured for this project')"
else
    echo "no mailbox on this machine"
fi

echo
echo "== graphify"
if [ -x tools/graphify_refresh.sh ]; then tools/graphify_refresh.sh --check; fi
