---
title: Docs Publishing
aliases: [Docs Export, Site Publishing, tess-docs-publish]
type: delivery
status: accepted
owner: phil
created: 2026-11-15
updated: 2026-11-15
tags: [delivery, process]
---

# Docs Publishing

> [!NOTE]
> Every commit in this vault ends up on the design site (`https://mindderivative.github.io/tess-shell/`) with no manual step. A hook starts `tess-docs-publish`, which exports the vault into `docs/` of the `tess-shell` repository, opens one pull request and turns on auto-merge. GitHub merges it when the required check `CI result` is green, and the merge deploys the site. Decided and built on 2026-11-15 at the maintainer's request: he had done the export, branch, pull request and merge by hand once and said he never wants to again.

## Purpose and scope

- In: the path from a vault commit to the live site, and what to do when it stops.
- Out: how the vault is converted for GitHub (`tools/sync_docs.py` in the `tess-shell` repository) and the site's build (`mkdocs.yml`, `docs.yml`).

## Behaviour

```mermaid
flowchart LR
  A[Vault commit] --> B[post-commit hook]
  B --> C[tess-docs-publish waits for 10 minutes of quiet]
  C --> D[Own clone: branch docs/vault-export on origin/main, sync_docs.py]
  D -->|docs/ changed| E[Commit, push, pull request, auto-merge]
  D -->|no change| F[Nothing to do]
  E --> G[CI result green]
  G --> H[GitHub squash-merges]
  H --> I[Deploy Docs workflow publishes the site]
```

| Part | Where | Does |
|---|---|---|
| Hook | `.git/hooks/post-commit` in the vault (not versioned) | Touches a time stamp and starts the publisher detached; never blocks a commit |
| Publisher | `~/.local/bin/tess-docs-publish` | Waits until the vault has been quiet for 10 minutes (`TESS_DOCS_QUIET`, seconds), so a run of commits makes one export; one run at a time (`flock`) |
| Its clone | `~/.cache/tess-shell-docs-publish/repo` | A shallow clone of `tess-shell`, used only by the publisher; the checkouts the code sessions work in are never touched |
| Branch and pull request | `docs/vault-export`, one open pull request | A new export force-pushes the same branch and updates the same pull request |
| Merge | GitHub auto-merge (squash) | The repository setting `allow_auto_merge` was turned on for this on 2026-11-15; the ruleset on `main` still applies in full (pull request, `CI result`, no bypass) |
| Site | `docs.yml` in `tess-shell` | Runs when `docs/` changes on `main` |

The publisher exports the vault's committed state (git `HEAD`), never uncommitted edits.

## Commands

| Command | Does |
|---|---|
| `tess-docs-publish` | What the hook runs: wait for quiet, then publish |
| `tess-docs-publish --now` | Publish at once |
| `tess-docs-publish --dry-run` | Stop before the commit and the push; prints how many files would change |

## Failure modes and recovery

| Failure | Result |
|---|---|
| `gh` not logged in, a push or pull request step fails, `sync_docs.py` fails | One line in `~/.cache/tess-shell-docs-publish/publish.log` and a critical desktop notification; the next vault commit tries again |
| CI on the pull request fails (for example the strict docs build finds a broken link) | The pull request stays open with auto-merge on; the next export replaces its content, so fixing the note in the vault and committing is the repair |
| Nothing changed in `docs/` | The run says so in the log and ends |
| Two exports overlap | The second sees the lock, ends, and the first run exports the newest state anyway |
| The machine is off | The hook did not run; the next commit exports everything |

## Facts that matter

- Delay: about ten minutes of quiet, then the CI run of the pull request (the `tess-shell` suite runs on it too, which takes a few minutes), then the deploy.
- The code sessions read specs from `docs/` of their own worktrees, which come from `origin/main`, so they see a note after the pull request merges. The vault is the source of truth.
- The earlier hook wrote the export into the `tess-shell` main checkout and left about 130 uncommitted files there. That is gone.
- `docs/` is generated: edit the vault, not the files in `docs/`.

## Questions After Testing

1. [ ] Should a docs-only pull request skip the `tess-shell` test shards? Context: `CI result` is required, so every export runs lint, four test shards and the package check, although only the docs build matters for it. A path filter inside `ci.yml` that still reports `CI result` would save the minutes. Recommendation: not now; the repository is public so the minutes are free, and the change touches the code repository's required check. Answered by: how long exports take to merge in the first week.

## Acceptance criteria

- [x] `tess-docs-publish --dry-run` exports into its own clone and reports the changed file count without pushing (run 2026-11-15, 133 files).
- [ ] A vault commit with no later commit for the quiet period opens or updates one pull request with auto-merge on, with nobody doing anything.
- [ ] After the merge the site shows the note (checked on the live site).
- [ ] A broken export shows in the log and as a notification.

## Links

[70 Delivery](70%20Delivery.md) · [Packaging and Session Start](Packaging%20and%20Session%20Start.md) · [Home](../00%20Home/Home.md)
