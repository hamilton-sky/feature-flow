# Forkboard

Review a design on its diagrams before the code is written.

A coding agent proposes two or three ways to build something, each with a mermaid flowchart. Forkboard turns that into one page people can read, edit and ask questions on, and gives the agent back what they did. It started as the brainstorm review page of [feature-flow](../../README.md), which still uses it, and is now its own package so it can grow without making the harness bigger.

Version 0.1.0 was the extraction: the same page feature-flow 0.25 made, behind a stable document format. 0.2.0 adds the Arrange button and four more themes that shape the boxes as well as the colours. See [Where it is going](#where-it-is-going) for what comes next.

![A Forkboard review page for a rate-limits brainstorm: the sidebar, option A's editable diagram and its pros, cons, size and risky areas](../../docs/forkboard.png)

## What the page does

- A sidebar that routes between the sections and options, and a system, light or dark switch.
- Flowcharts you can edit: **Arrange** the boxes left to right, top to bottom, radial or as a grid, drag boxes, add boxes of seven kinds, colour them from 12 colours, rename, connect, delete, undo and redo (with the keyboard too), reset, and copy back as mermaid. Other diagrams are drawn by mermaid.
- Six themes, each with a light and a dark side. `forkboard themes` lists them and what each suits:

  | Theme | Suits |
  |---|---|
  | `route` | the default: most features |
  | `blueprint` | architecture, backends, system design |
  | `sketch` | early, fuzzy ideas: handwriting and hand-drawn lines |
  | `paper` | decisions to share or print: editorial, square, thin ink |
  | `terminal` | infrastructure, CLIs, dev tools: monospaced, square |
  | `bright` | consumer apps and UI: round, thick, colourful |

  A theme is one CSS file in [forkboard/themes/](forkboard/themes/): colour and font tokens, a `/* suits: */` line, and optional box tokens (`--node-radius`, `--node-stroke`, `--node-font`, `--node-filter`, `--edge-width`, `--edge-filter`; `url(#fb-rough)` draws lines by hand). Adding one is adding a file.
- **Live** (claude.ai only): published as an artifact that saves itself, everyone it is shared with can save their own version of each diagram, compare any version with the original, ask Claude to redraw a diagram, and send questions to the session that made the page. The session reads them with `forkboard asks`, answers with `forkboard answer`, and takes a version with `forkboard version`.

Everything is escaped except a small markdown: paragraphs, lists, tables, code, `code`, **bold**, *em* and https links. Nothing is sent anywhere; the page loads its fonts from Google Fonts, and mermaid from jsDelivr only for a diagram that is not a flowchart.

## Use

```
forkboard render review.json [--theme NAME] [--fragment] [--out page.html]
forkboard live review.json live/            # live/index.html and live/state.json, to publish together
forkboard asks live/                         # the open questions, with each asker's version of the diagram
forkboard answer live/ 1 "Yes, for exports over 10k rows."
forkboard version live/ 2 u_dana             # that person's version of figure 2, as mermaid
forkboard themes                             # each theme and what it suits
```

`render -` reads the document from stdin and writes the page to stdout. `--fragment` leaves out the doctype, html, head and body tags, for a host that adds its own. `live` keeps what people saved in a `state.json` already in the folder, so each round keeps their versions and questions.

It is standard-library Python 3.9+, with no dependencies. `python -m forkboard` works too.

## The review document

A tool hands Forkboard a JSON document; Forkboard never reads or writes the tool's own files.

```json
{"schema": "bundle/1",
 "id": "csv-export",
 "kind": "Brainstorm",
 "title": "Brainstorm: CSV export",
 "meta": {"picked by": "person"},
 "intro": "markdown",
 "sections": [
   {"title": "Options", "kind": "text", "markdown": "",
    "items": [{"title": "A. Stream it", "label": "A", "chosen": false,
               "markdown": "```mermaid\nflowchart LR\n  Admin --> Api\n```"}]},
   {"title": "Chosen", "kind": "chosen", "markdown": "A, because exports are small."}]}
```

A section's `kind` is `text`, `chosen`, `rejected`, `open` or `callout`. Figures are numbered in the page's order from 1. Each figure in `state.json` keeps a fingerprint of the diagram it was built from, so a tool writing a version back can refuse when its own copy changed since. A reader refuses a document whose schema major it does not know. The full description is in [forkboard/doc.py](forkboard/doc.py).

## How feature-flow uses it

feature-flow's `brainstorm-page` reads the brainstorm's own conventions (its Chosen, Rejected and Open sections, and which option the Chosen line picks) into a review document, and calls Forkboard to make the page. Writing a version back into `brainstorm.md` is feature-flow's job. Every feature-flow install carries a copy of Forkboard inside its package (`feature_flow/_forkboard/`), so the brainstorm page works under `python3 -I` and needs nothing extra installed.

## Tests

```
python3 -m unittest discover -s packages/forkboard/tests     # from the repository root
cd packages/forkboard/tests/browser && npm install && npm test   # the page in Chromium
python3 packages/forkboard/tests/package_smoke.py               # build, install in a fresh venv, run
```

## Where it is going

The [proposal](https://claude.ai/artifact/2tGHswZqdnnq4b6YhADRJw) has the whole plan. In short:

- 0.3: a verdict the agent reads back (`verdict.json`): the pick, each figure's final diagram, and comments pinned to boxes and arrows, typed as question, concern, suggestion or blocker. A round diff with a legend, not colour alone.
- 0.4: MCP tools (`open_review`, `get_verdict`), so any agent can use it.
- 0.5: the disagreement map (every reviewer's version on one canvas), lens overlays, and a local server host besides the claude.ai one.
- Then its own repository, once someone outside uses it.

## License

MIT
