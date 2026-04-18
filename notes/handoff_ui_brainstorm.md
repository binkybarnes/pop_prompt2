# Handoff — Reorder Alert UI brainstorm (mid-session)

Paused mid-brainstorm so user could switch computers. A separate Claude is concurrently working on pipeline step 05 promotion / tweaks (see `notes/status.md` for the pipeline side).

## Where we are in the superpowers brainstorming flow

Skill in use: `superpowers:brainstorming`. Visual companion is active (server started at http://localhost:51015 — will need restart on the new machine). Step currently in_progress: **#3 Ask clarifying questions one at a time**.

Remaining brainstorming steps (in order):
1. Finish clarifying questions (one left — see below)
2. Propose 2–3 approaches with tradeoffs (#4)
3. Present design sections, get user approval (#5)
4. Write design doc to `docs/superpowers/specs/2026-04-18-reorder-alert-ui-design.md` (#6)
5. Self-review + user review of the spec (#7)
6. Invoke `superpowers:writing-plans` skill (#8)

## Decisions locked so far

| Q | Decision |
|---|---|
| Audience / phasing | **C — phased.** Build the utility table first (fast, unblocks the UI Claude), then layer polish + before/after story on 2–3 showcase SKUs for the demo. |
| Tech stack | **B — Next.js + React.** Bake `reorder_alerts.xlsx` → JSON as an extra step at the end of pipeline notebook 09 so the UI is a static-ish client reading JSON, not parsing xlsx in-browser. |
| Visual reference | **Linear** (linear.app). User supplied 2 screenshots in `web_images/`: issues list + issue detail with right-hand properties panel. **Deviation:** do NOT copy Linear's hidden-filter pattern — buyers want filter chips visible above the table (DC, confidence, alert-status). |

## Open question (where we paused)

**Q4 — scope of the shell.** Waiting on user's pick:
- **A.** F1 only. Single app, list + detail.
- **B.** (my recommendation) F1 now, leave room for F2 later. Two-tab shell ("Reorder Alerts" | "Demand Curves"), only tab 1 is built.
- **C.** F1 + F2 both built (doubles scope).

Next action on resume: ask Q4, then move to step #4 (propose approaches).

## Project context the resuming agent needs

- Source of truth for the feature is `notes/feature_tree_v2.md` (F1 spec, decisions locked, build order).
- F1 output shape is defined in `feature_tree_v2.md` line ~41: one row per alerted SKU×DC with columns `SKU, DC, on_hand, available, organic_run_rate, lead_time, reorder_point, suggested_qty, confidence, why`.
- Pipeline step 09 (`pipeline/09_reorder_alerts.ipynb`) is the notebook that will produce `reorder_alerts.xlsx`. Not built yet. User plans to build step 09 themselves while the UI Claude works in parallel.
- The UI Claude will work in a **separate session** and only needs to consume the output file — it does NOT need the pipeline context.
- Project conventions: Python env is `mamba run -n 3.11mamba …`. Data gitignored. Notebooks edited with `NotebookEdit`.

## Gitignore / filesystem notes still pending

User asked about "how to handle gitignores in a subfolder" — not yet answered. Plan (to propose as part of the design):
- Put the UI at `ui/` under project root.
- Add `ui/node_modules/`, `ui/.next/`, `ui/out/` to root `.gitignore`.
- Or: commit a `ui/.gitignore` with just those entries (more self-contained, easier for the UI Claude to bootstrap).
- Also: add `.superpowers/` to root `.gitignore` (companion server writes there).

## Companion server

- URL on previous machine: http://localhost:51015 (dead after machine switch)
- Screen dir was: `.superpowers/brainstorm/14675-1776534000/content`
- To resume visuals: restart with `scripts/start-server.sh --project-dir /path/to/pop_prompt2` from the brainstorming skill scripts dir.
- No visual mockups were written — only terminal conversation so far.
