# POP Reorder Intelligence UI

Static Next.js prototype on top of F1 reorder-alert data. See `docs/superpowers/specs/2026-04-18-reorder-alert-ui-design.md` for the design doc.

## Dev

```
cd ui && npm install && npm run dev
```

Then open http://localhost:3000.

## Build

```
npm run build
```

Outputs a static site to `ui/out/`.

## Data

JSON artifacts live in `ui/data/` and are committed. They are produced by pipeline notebooks 09 and 10.
