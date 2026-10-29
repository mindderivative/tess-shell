---
title: Open Questions
aliases: [Open Items, Unknowns]
type: moc
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [moc, question]
related: ["[[Home]]", "[[Roadmap]]", "[[Risk Register]]", "[[Index]]"]
depends_on: []
---

# Open Questions

> [!summary]
> The one place to find every open item and every claim not yet verified. Each section below is embedded from the note that owns it, so this page never holds a second copy (one source of truth, [[AGENTS#2. Hard rules]] rule 4). Resolved items stay visible as checked boxes. A new unknown goes in its own note's open section and, if it needs a home, here ([[AGENTS#11. Session workflow]]).

## Unverified Claims

Every claim tagged `#needs-verification`, grouped by folder. **Where** links to the section that holds the claim, **Claim** is the sentence the tag follows, and **To verify** is what the text after the tag says to check (empty when the tag stands alone). The table is built by Dataview from the notes themselves, so it never goes stale and holds no copy of a claim.

> [!note] Needs JavaScript queries
> The table uses a `dataviewjs` block. In Dataview's settings, turn on "Enable JavaScript Queries"; until then the block shows an error and the plain list below still works.

```dataviewjs
const TAG = "#needs-verification";
const pages = dv.pages('#needs-verification AND -"copilot"')
  .where(p => p.file.name != "Open Questions" && p.file.name != "AGENTS" && p.status != "superseded")
  .sort(p => p.file.path, "asc");

const clean = (s) => s
  .replace(TAG, "")
  .replace(/!?\[\[([^\]|]*)\|([^\]]*)\]\]/g, "$2")
  .replace(/!?\[\[([^\]]*)\]\]/g, "$1")
  .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
  .replace(/\*\*|__/g, "")
  .replace(/^\s*(>\s*)*([-*]|\d+\.)\s+(\[.\]\s+)?/, "")
  .replace(/^\s*>\s*/, "")
  .replace(/\s+/g, " ")
  .trim();

const sentences = (t) => t.split(/(?<=[.!?])\s+(?=[A-Z(`*\[])/);
const cut = (t, n) => t.length > n ? t.slice(0, n - 1).trimEnd() + "…" : t;

// Returns [claim, toVerify]: the sentence the tag follows, and what the text after the tag asks to check.
const describe = (line) => {
  const raw = line.replace(/`[^`]*`/g, m => m.replace(/#/g, "\u0023"));
  const at = raw.indexOf(TAG);
  let before = raw.slice(0, at), after = raw.slice(at + TAG.length);
  if (line.trim().startsWith("|")) {
    const cells = line.trim().replace(/^\||\|$/g, "").split("|").map(c => clean(c)).filter(c => c.length);
    return [cut(cells.join(" · "), 160), ""];
  }
  before = clean(before);
  after = clean(after).replace(/^[:,;\s-]+/, "");
  const parts = sentences(before);
  let last = parts.pop() || before;
  if (last.length < 45 && parts.length) last = parts.pop() + " " + last;
  const tail = (sentences(after)[0] || "").replace(/[.]$/, "");
  return [cut(last, 170), cut(tail, 110)];
};

const anchor = (h) => h.replace(/[#|^:%\[\]]/g, " ").replace(/\s+/g, " ").trim();

const groups = new Map();
let total = 0;
for (const p of pages) {
  const text = await dv.io.load(p.file.path);
  if (!text) continue;
  const body = text.replace(/^---\n[\s\S]*?\n---\n/, "");
  let heading = null, fence = false;
  for (const line of body.split("\n")) {
    if (/^\s*```/.test(line)) { fence = !fence; continue; }
    if (fence) continue;
    const h = line.match(/^#{1,6}\s+(.*)$/);
    if (h) { heading = h[1].trim(); continue; }
    if (!line.replace(/`[^`]*`/g, "").includes(TAG)) continue;
    const [claim, check] = describe(line);
    const short = heading ? cut(heading.replace(/\s*\([^)]*\)\s*$/, ""), 42) : "";
    const label = heading ? p.file.name + " › " + short : p.file.name;
    const link = dv.fileLink(heading ? p.file.path + "#" + anchor(heading) : p.file.path, false, label);
    const area = p.file.folder ? p.file.folder.split("/")[0] : "Vault";
    if (!groups.has(area)) groups.set(area, []);
    groups.get(area).push([link, claim, check]);
    total++;
  }
}
dv.paragraph("**" + total + " claims** in " + pages.length + " notes still need a source or a test.");
for (const [area, rows] of [...groups.entries()].sort()) {
  dv.header(3, `${area} (${rows.length})`);
  dv.table(["Where", "Claim", "To verify"], rows);
}
```

### Notes Only

The same notes as a plain list, with no JavaScript:

```dataview
LIST
FROM #needs-verification AND -"copilot"
WHERE file.name != "Open Questions" AND file.name != "AGENTS" AND status != "superseded"
SORT file.name ASC
```

## Vision

### [[Personas and Use Cases]]

![[Personas and Use Cases#Open questions]]

## Architecture

### [[System Context]]

![[System Context#Open questions]]

### [[Layers and Components]]

![[Layers and Components#Open questions]]

### [[Process Model and Threading]]

![[Process Model and Threading#Open questions]]

### [[Data Flow]]

![[Data Flow#Open questions]]

## Decisions

### [[ADR-0001 Shell Surface Strategy]]

![[ADR-0001 Shell Surface Strategy#Open items]]

### [[ADR-0007 Shell UI Layer]]

![[ADR-0007 Shell UI Layer#Open items]]

## Surfaces

### [[Surface Types]]

![[Surface Types#Open questions]]

### [[Bar]]

![[Bar#Open questions]]

### [[Frame]]

![[Frame#Open questions]]

### [[Panel]]

![[Panel#Open questions]]

### [[Popup]]

![[Popup#Open questions]]

## Modules and Runtime

### [[Clock Module]]

![[Clock Module#Open questions]]

### [[Shell Start and Stop]]

![[Shell Start and Stop#Open questions]]

### [[Config Discovery and Registry]]

![[Config Discovery and Registry#Open questions]]

### [[Validation and Errors]]

![[Validation and Errors#Open questions]]

### [[Hot Reload]]

![[Hot Reload#Open questions]]

### [[IPC and CLI]]

![[IPC and CLI#Open questions]]

### [[Logging]]

![[Logging#Open questions]]

### [[Wayland Protocols]]

![[Wayland Protocols#Open Questions]]

### [[Expression Language Requirements]]

![[Expression Language Requirements#Open questions]]

## YAML Reference

### [[Common Keys and Conventions]]

![[Common Keys and Conventions#Open]]

### [[Shell File]]

![[Shell File#Open]]

### [[Module File]]

![[Module File#Open]]

### [[Style, Theme and Stylesheet Files]]

![[Style, Theme and Stylesheet Files#Open]]

### [[Style Schema]]

![[Style Schema#Open]]

### [[Settings File]]

![[Settings File#Open]]

### [[JSON Schema and Editor Support]]

![[JSON Schema and Editor Support#Open]]

## Python API

### [[Module Contract]]

![[Module Contract#Open questions]]

### [[Module Context]]

![[Module Context#Open questions]]

### [[Python Builder]]

![[Python Builder#Open questions]]

### [[Value Types and Conversion]]

![[Value Types and Conversion#Open questions]]

## Design System

### [[Building Blocks]]

![[Building Blocks#Open]]

### [[V1 Widgets]]

![[V1 Widgets#Open questions]]

## Engine Requests

### [[TRE-REQ-001 Layer Surface Window]]

![[TRE-REQ-001 Layer Surface Window#Open items]]

### [[TRE-REQ-005 Keep-Alive and Loop Stop]]

![[TRE-REQ-005 Keep-Alive and Loop Stop#Open questions]]

## Research

### [[D-Bus Libraries for Python]]

![[D-Bus Libraries for Python#Open]]

### [[Logging with Loguru]]

![[Logging with Loguru#Open]]

### [[Shadows on Layer Surfaces]]

![[Shadows on Layer Surfaces#To research]]

## Links

- [[Home]] · [[Roadmap]] · [[Risk Register]] · [[Index]]
