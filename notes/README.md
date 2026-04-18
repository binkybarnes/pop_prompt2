# notes/ — project docs index

Every Claude Code chat in this repo auto-loads `CLAUDE.md`. This file is the index of everything else. Read the files below before starting a task that touches that area — it's how a fresh chat catches up without you having to re-explain.

## Read order for a fresh chat

1. `CLAUDE.md` (auto-loaded at session start) — project context, conventions, key domain terms
2. This file
3. `feature_tree_v2.md` — the locked spec (two features + shared pipeline)
4. `data_notes.md` — what the real data actually looks like
5. `status.md` — what's currently in progress / blocked / next
6. Whichever of the rest is relevant to the task

## File index

- **feature_tree_v2.md** — **SPEC**. Two headline features (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases of the demand curve, revised 48 hr build order. Start here for any implementation question.
- **feature_tree.md** — original MoSCoW brainstorm (F0–F13). Kept as reference; `feature_tree_v2.md` supersedes it. Do not edit.
- **data_notes.md** — concrete shape of the data (row counts, column names, SKU coverage, known data-quality issues, gotchas). Read before writing any load / join / dedup code.
- **manual_demand_inference.md** — how POP buyers do reorder math today, and how our tool replaces it. Background for F1.
- **prompt1_notes.md** — original Problem 1 (Demand & Order Intelligence) brief, vocabulary, inferred problems.
- **prompt2_notes.md** — original Problem 3 (Inventory & Fulfillment) brief. Mostly out of scope for MVP.
- **data_dictionary.md** — per-file column meanings and tier rankings (which files we use, which we skip).
- **execution_plan.md** — 5-layer architecture + team split + original 48 hr schedule. Superseded in part by `feature_tree_v2.md` build order but still useful for the layer framing.
- **status.md** — rolling "what's in progress / blocked / next." Short. Update after finishing a pipeline step or hitting a blocker.
- **chats/** — exported Claude conversations. Archaeology only; don't treat as authoritative.

## How to keep this useful

- When you finish a pipeline step, update `status.md`.
- When you discover something about the data that wasn't obvious, append to `data_notes.md`.
- When a decision gets locked (not while brainstorming), update `feature_tree_v2.md`.
- Don't silently delete docs — if something is wrong, correct it and leave a pointer to what replaced it.
