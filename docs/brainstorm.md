# Brainstorming a feature, and the review page

This page walks through a brainstorm from your side of the chat, then shows Forkboard, the package that draws the review page. The rules the session follows are in [guides/brainstorm.md](../guides/brainstorm.md); the [README](../README.md#brainstorm-before-planning) has the summary.

## When to brainstorm

Brainstorm when you know what you want but not how to build it: there are two real ways to do it, or you can't yet say what "done" looks like. Skip it for a small, clear change. The session also offers it on its own when an idea looks fuzzy, and it always brainstorms in `careful`.

## A brainstorm, step by step

In a Claude Code session in your repo (Codex: `$feature-flow` instead of `/feature-flow`):

```
/feature-flow rate-limits brainstorm
```

1. **Questions.** The session asks up to three, one at a time, and only what the code can't tell it: who it is for, what success looks like, what is off limits.
2. **A look around.** A scout reads how your code does the nearest thing today and which files would change. A web scout looks up prior art when the idea leans on an outside library or a known hard problem.
3. **Options.** Two or three ways to build it that really differ. Each one has a mermaid diagram, two or three pros and cons, a rough size and its risky areas. Helpers can weigh in: the architect, designer or product owner, a skeptic who attacks each option, and lenses (`positive`, `researcher`, `open-minded`, `artistic`, `ux`, `security`).
4. **The review page.** The session shows the options as one page and recommends one. It writes the page beside the brainstorm (`.feature-flow/state/brainstorm-<feature>.html`) and opens it, or publishes it as an artifact when it can.
5. **Your pick.** Answer in the chat: pick one, mix two, change one, or drop the brainstorm. The same yes approves the brief that follows, so you approve once.

The brainstorm is saved as `.feature-flow/state/brainstorm-<feature>.md` and committed with the plan as `plans/<feature>/brainstorm.md`. The planner builds the option you chose, and the plan reviewer fails a plan that builds a rejected one.

## Using the page

- **Read.** The sidebar jumps between sections and options. Switch between system, light and dark at its foot.
- **Edit a diagram.** Drag boxes. **Add box** (its arrow picks one of seven kinds and a colour), double-click a box to rename it, **Connect** two boxes, **Delete**, **Undo** and **Redo** (Ctrl+Z and Ctrl+Shift+Z), **Reset**. Edits stay in your browser.
- **Keep an edit.** **Copy as mermaid** copies the edited diagram. Paste it into the chat to change an option.
- **Look.** `route` is the default style. Ask for `blueprint`, or put `Style: blueprint` in the brainstorm.

## The live page (Claude only)

When the session can publish artifacts, the page is live: a link you can share from its Share menu. The people you share it with need a claude.ai sign-in and edit access, not Claude Code.

- **Save as my version** keeps your version of a diagram on the page, for everyone. Pick anyone's version from the list.
- **Compare with original** marks added, removed and renamed boxes and arrows.
- **Ask Claude to change it** redraws one diagram with your own Claude.
- **Talk to Claude** sends the session a question. Each save wakes the session: it answers on the page, can put someone's version into the brainstorm, and publishes the next round to the same link.

To draw first, start with `/feature-flow rate-limits brainstorm sketch`. The page opens with a small sketch of the idea; you change it, save it and send it, and the options build on your drawing.

## Forkboard on its own

The page is drawn by **Forkboard** ([packages/forkboard/](../packages/forkboard/)). feature-flow carries its own copy, so a brainstorm needs nothing extra. To make the page by hand:

```bash
feature-flow brainstorm-page rate-limits                    # writes .feature-flow/state/brainstorm-rate-limits.html
feature-flow brainstorm-page rate-limits --style blueprint
python3 scripts/flow-status.py rate-limits --brainstorm-page   # the same, from a repo install
```

Forkboard also works without feature-flow, from any JSON review document:

```bash
forkboard render review.json --out page.html
forkboard live review.json live/          # index.html and state.json, to publish as an artifact
forkboard asks live/                      # open questions, each with the asker's version of the diagram
forkboard answer live/ 1 "Yes, for exports over 10k rows."
forkboard version live/ 2 u_dana          # someone's version of figure 2, as mermaid
```

The document format and the rest are in [Forkboard's README](../packages/forkboard/README.md).

## What has not been tried yet

The brainstorm has had no real run on a project yet, and the live page's loop (a person saves, the session wakes, answers and publishes again) has only run against a stand-in in tests. If you try either, [docs/field-run.md](field-run.md) says what to send back.
