---
title: Docs Site Plan
aliases: [Docs Site, GitHub Pages plan, Documentation Site]
type: delivery
status: accepted
owner: phil
created: 2026-11-19
updated: 2026-11-19
tags: [delivery/docs]
---

# Docs Site Plan

> [!NOTE]
> The public site, https://mindderivative.github.io/tess-shell/, is today a copy of this vault ([Docs Publishing](Docs%20Publishing.md)): a reader who wants to install the shell and write a Bar finds design notes, not a product. The maintainer asked on 2026-11-19 for it to be modelled on the tre and Tesserae UI sites. This note sets the structure, what is reused from what already exists in the `tess-shell` repository, what is new, and how the vault export fits in as one section. The vault session, not `tess-shell`, builds it (maintainer, 2026-11-19), in its own clone of the repository. Drafted by the vault session from the three sites' navigation and the repository's own files; nothing here was built or run in the vault.

## What the Other Sites Do

| | tre (`tess-re`) | Tesserae UI (`tess-ui`) | tess-shell today |
|---|---|---|---|
| Start | Overview, Installation, Getting Started | Overview with a short example, Installation, Getting Started, two Tutorials | The design vault's Home |
| Learn | Guide (14 pages) and Examples | Guide (about 30 pages) | Nothing on the site; a user guide of 10 pages sits in the repository's `guide/` |
| Look up | API (Rust, Python) and a Reference of one page per type | Components, Stylesheets and API, generated from the code by `tools/generate_component_docs.py` | The TDL reference notes in `41 TDL Reference`, written as design |
| Understand | Architecture, Design (11 pages) | Architecture | `20 Architecture` and 38 ADRs |
| Change | Upgrading (a page per release) | Migration, Changelog | `CHANGELOG.md`, not on the site |
| Theme | Material for MkDocs | Material for MkDocs, same palette | Material, same palette |

Both sites open with what the thing is in one sentence, a working example in the first screen, and links onward; nothing there is a design record. tre keeps its design notes in a Design section at the end, which is the model for the vault export.

## What Already Exists (read in the `tess-shell` repository, 2026-11-19)

- `README.md` (352 lines): what it is and how to install it.
- `guide/` (10 pages, about 5,800 lines): Install and start, The configuration folder, Your first Bar, Surfaces, Modules, Styling and themes, settings, Keyboard and shortcuts, The command line, Troubleshooting. Its tables of keys, defaults, tokens, settings and commands are generated from `tesserae-shell schema --json` and the command-line parser by `tests/guide_tables`; every example is a real folder in `guide/examples/` that a test runs through `check`. This is the strongest asset: it only needs to be on the site.
- `CHANGELOG.md` (310 lines).
- The vault's `42 Python API`, `41 TDL Reference`, `20 Architecture`, `70 Delivery` and `60 Quality` notes, written as design.

## The Structure

```
Overview                          index.md             what it is, a 10-line Bar, a screenshot, links
Installation                      installation.md      pip or uv, the session unit, first run, uninstall
Getting Started                   getting-started.md   the configuration folder and a first Bar
Tutorial                          tutorial.md          a shell built step by step (new)
Guide
  The configuration folder        guide/configuration-folder.md
  Surfaces                        guide/surfaces.md
  Modules                         guide/modules.md
  Styling and themes              guide/styling.md
  Settings                        guide/settings.md
  Keyboard and shortcuts          guide/keyboard.md
  Multiple monitors               guide/monitors.md              (new, from the Monitor notes)
  Start with your session         guide/session.md               (from Packaging and Session Start)
  Hot reload                      guide/hot-reload.md            (new, short)
  Writing a module                guide/writing-a-module.md      (new, from 42 Python API)
  Security and trust              guide/security.md              (new, from Security Model)
  The command line                guide/command-line.md
  Troubleshooting                 guide/troubleshooting.md
Examples                          examples.md          every folder in guide/examples/, with its check status
Reference                         reference/           generated from the schema, one page per block
  Shell file blocks               Shell, Monitor, Bar, Frame, Panel, Popup, Module, Style, Stylesheet, Theme, Settings
  Values and enums                tokens, enums, four-sided values, Size values
  Commands and exit codes         from the parser
  Messages                        every finding `check` prints, by name
API
  Python module API               Module Contract, Context, Events and Actions
  Python builder                  the Python builder and the value types
Architecture                      architecture.md      one page: the process, the loop, the services, the layers
Upgrading                         upgrading.md         migrate, the version policy, deprecations; the CHANGELOG
Design                            design/              the vault export: vision, architecture, ADRs, specifications
Contributing                      contributing.md
```

## What Is New and What Is Moved

| Page | Source | Work |
|---|---|---|
| Overview, Installation, Getting Started | `README.md`, guide pages 01 to 03 | Rewrite for a first-time reader; add a screenshot |
| Guide pages | `guide/*.md` | Move to `docs/guide/` and rename without the numbers; keep the generated markers and the tests working |
| Tutorial | New | One shell from nothing: a Bar and a Clock, then a Panel with the Launcher, a Popup, a style of your own, a module of your own. Every step is a folder under `guide/examples/` that `check` runs |
| Multiple monitors, Hot reload, Security and trust, Start with your session | The vault notes in `40 Specifications`, `60 Quality`, `70 Delivery` | Rewrite for a user, one page each, no design argument |
| Writing a module | `42 Python API` | A user guide: a module file, its Python, the context, an action, a test with `check` |
| Reference | `tesserae-shell schema --json` | A generator, as Tesserae UI does for components: one page per block with every key, type, default, allowed values and the version it appeared in, and a page per enum; written to `docs/reference/` and compared by a test, like `guide_tables` |
| Messages | The finding names in the code | One page: every finding the shell prints, its meaning and what to do |
| Architecture | `20 Architecture` | One user-level page that links into Design for the detail |
| Upgrading | `CHANGELOG.md`, [Version Policy and Migration](Version%20Policy%20and%20Migration.md) | The changelog on the site, the policy, `migrate` |
| Design | The vault export | Written to `docs/design/` instead of `docs/` |

## How the Pieces Fit

- `docs/` becomes the hand-written site. The vault export goes to `docs/design/`. Its links are relative, so moving the whole tree down one folder keeps them valid; the export's own `README.md` becomes `design/index.md`.
- `tools/sync_docs.py` writes and prunes only inside `docs/design/`, so a vault commit never touches a hand-written page. The export tool `tess-docs-publish` (the vault session's) is changed to match once the repository changes: it stages `docs/design/` only.
- The status icons of the design notes (draft, review, accepted, stable) stay, but only for pages under `design/`.
- The site is built from `main` and describes the code on `main`. Pages mark what is not in the released version, as the guide does now (`tess-shell` already marks "added after 0.1.2"). No per-version site until there are several releases to keep.
- `mkdocs build --strict` stays in CI, so a broken link in any page fails the pull request.
- The navigation (`nav:`) is written by hand in `mkdocs.yml`, as tre and Tesserae UI do, with the Reference pages added by the generator the way Tesserae UI marks its generated block.
- The guide's note "design notes are in `docs/`" changes to point at `design/`.

## Who Does What

| Task | Owner |
|---|---|
| The tree move, the pages, the tutorial, the generator, the navigation, the tests, the CI check | Vault session (maintainer, 2026-11-19) |
| `sync_docs.py` writing to `docs/design/` | Vault session |
| The user-level rewrites (Security, Monitors, Session, Python API) | Vault session, from the vault notes and the code |
| `tess-docs-publish` staging `docs/design/` only | Vault session, after the repository change merges |
| Screenshots | Vault session, from a private sway, replaced later with KWin captures |

## Open Questions

1. [x] Where do the screenshots come from? Context: tre and Tesserae UI show their output; a shell is a picture. The code session can capture the Bar, a Panel, a Popup and the Launcher from the private sway with `grim`, but KWin draws the Frame and the shadows differently, and the maintainer's KWin is the look that counts. Recommendation: the code session captures a first set from the private sway now so the pages are complete, marked as such; the maintainer replaces them with KWin captures later (he names which).
2. [x] Should the Design section stay on the public site? Context: tre keeps its design notes there. Recommendation: yes, last in the navigation, labelled as the design record, so a reader who wants the reasoning can reach it.
3. [x] How large is the tutorial for the first version? Recommendation: one tutorial of five steps (Bar and Clock; a Panel and the Launcher; a Popup from a Tray; a style of your own; a module of your own), each step a folder checked by `check`.
4. [x] Is the Python API page hand-written or generated from docstrings? Context: the module API is small (the context, events, actions); a docstring generator adds a dependency ([ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)). Recommendation: hand-written, with the signatures checked by a test that imports them.
5. [x] Does the site name the project as pre-alpha? Recommendation: yes, one line on the Overview, as the guide does.

All five questions answered by the maintainer on 2026-11-19: screenshots from the private sway first is fine, and 2 to 5 as recommended.

## Acceptance Criteria

- [ ] The Overview shows what the shell is, a working example and a screenshot in the first screen, with links to Installation, Getting Started and the Tutorial.
- [ ] Installation takes a reader from nothing to a running Bar on KDE Plasma, including starting with the session and uninstalling.
- [ ] Every Guide page is a user page; no page argues a design decision, and each links to Design for it.
- [ ] Every Reference page is generated from the schema and a test fails if it is stale.
- [ ] Every example and every tutorial step is a folder that `tesserae-shell check` passes.
- [ ] `mkdocs build --strict` passes and the navigation reaches every page.
- [ ] A vault commit changes only `docs/design/`.

## Links

[Docs Publishing](Docs%20Publishing.md) · [Packaging and Session Start](Packaging%20and%20Session%20Start.md) · [Version Policy and Migration](Version%20Policy%20and%20Migration.md) · [70 Delivery](70%20Delivery.md)
