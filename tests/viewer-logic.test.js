// usage: node tests/viewer-logic.test.js scripts/flow-view.html
// unit tests for the pure layout and replay functions inside the viewer page.
// prints one line per check, "ok" or "FAIL", and exits 1 if any failed.

const fs = require("fs");

const html = fs.readFileSync(process.argv[2], "utf8");

function block(name) {
  const a = html.indexOf("// <" + name + ">");
  const b = html.indexOf("// </" + name + ">");
  if (a < 0 || b < 0) throw new Error("missing block " + name);
  return html.slice(a, b);
}

const api = new Function(block("layout") + "\n" + block("replay") + "\nreturn { layoutGraph, buildFrames, readyOf };")();

let failed = 0;
function check(name, cond) {
  console.log((cond ? "ok   " : "FAIL ") + name);
  if (!cond) failed++;
}

const O = { nodeW: 200, nodeH: 60, colGap: 80, rowGap: 20, pad: 30 };
const T = (id, blocked) => ({ id: id, label: String(id).padStart(2, "0"), blocked_by: blocked.map((b) => String(b).padStart(2, "0")), status: "open" });

const diamond = [T(1, []), T(2, [1]), T(3, [1]), T(4, [2, 3])];
const L = api.layoutGraph(diamond, O);
const layerOf = (l) => L.nodes[l].layer;
check("every dependency points from an earlier column to a later one", L.edges.every((e) => layerOf(e.from) < layerOf(e.to)));
check("a ticket sits one column after its latest blocker", layerOf("04") === 2 && layerOf("02") === 1 && layerOf("01") === 0);
check("the diamond has four edges", L.edges.length === 4);

const overlap = (a, b) => Math.abs(a.x - b.x) < O.nodeW && Math.abs(a.y - b.y) < O.nodeH;
const labels = Object.keys(L.nodes);
let clash = false;
for (let i = 0; i < labels.length; i++) for (let j = i + 1; j < labels.length; j++) if (overlap(L.nodes[labels[i]], L.nodes[labels[j]])) clash = true;
check("no two tickets overlap", !clash);
check("the canvas is as wide as its columns", L.width === O.pad * 2 + 3 * O.nodeW + 2 * O.colGap);
check("the layout is deterministic", JSON.stringify(api.layoutGraph(diamond, O)) === JSON.stringify(L));

const crossing = api.layoutGraph([T(1, []), T(2, []), T(3, [2]), T(4, [1])], O);
check("ordering removes an avoidable crossing", crossing.nodes["04"].y < crossing.nodes["03"].y);

const cyc = api.layoutGraph([T(1, [2]), T(2, [1])], O);
check("a dependency cycle does not hang and still places both tickets", !!cyc.nodes["01"] && !!cyc.nodes["02"]);
const missing = api.layoutGraph([T(1, [9])], O);
check("a blocker that does not exist is ignored", missing.edges.length === 0 && !!missing.nodes["01"]);
check("a single ticket lays out", api.layoutGraph([T(1, [])], O).width === O.pad * 2 + O.nodeW);

const ready = api.readyOf(diamond, { "01": "resolved", "02": "open", "03": "open", "04": "open" });
check("a ticket is ready when open and all blockers are resolved", ready["02"] && ready["03"] && !ready["04"] && !ready["01"]);
const ready2 = api.readyOf(diamond, { "01": "resolved", "02": "claimed", "03": "resolved", "04": "open" });
check("a claimed ticket is not ready, and one blocker still open keeps 04 waiting", !ready2["02"] && !ready2["04"]);

const details = {
  "01": { history: [{ t: 10, status: "open" }, { t: 20, status: "resolved" }] },
  "02": { history: [{ t: 10, status: "open" }, { t: 30, status: "resolved" }, { t: 40, status: "open" }, { t: 50, status: "resolved" }] },
};
const frames = api.buildFrames(diamond, details);
check("the replay starts from each ticket's first recorded state", frames[0].state["01"] === "open" && frames[0].change === null);
check("every status change becomes one frame", frames.length === 1 + 4);
check("frames are in time order", frames.every((f, i) => i === 0 || f.t >= frames[i - 1].t));
check("a ticket being sent back is its own frame", frames.some((f) => f.change && f.change.label === "02" && f.change.from === "resolved" && f.change.to === "open"));
check("the last frame holds the final committed state", frames[frames.length - 1].state["01"] === "resolved" && frames[frames.length - 1].state["02"] === "resolved");
check("tickets with no history stay open throughout", frames.every((f) => f.state["03"] === "open"));
check("no history means a single frame", api.buildFrames(diamond, {}).length === 1);

process.exit(failed ? 1 : 0);
