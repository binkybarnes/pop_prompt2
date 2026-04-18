● Found it — it's a unit-of-measure bug, not joins.

  What's actually happening

  The 4 files don't all measure inventory the same way:

  ┌──────────────────────┬──────────────────────────────────────────────────────────────────────┐
  │         File         │                             What 1 means                             │
  ├──────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ inv_snapshot On Hand │ 1 = 1 patch (base unit — individual piece)                           │
  ├──────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ sales QUANTITY_adj   │ 1 = 1 CASE (or box, or bag — varies per row; row says which in UOFM) │
  ├──────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ sales QTYBSUOM       │ Number of base units per one of those cases/boxes (the case pack)    │
  ├──────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ po QTY Shipped       │ 1 = 1 patch (base units)                                             │
  ├──────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ transfers TRX QTY    │ mixed — U Of M column says BOX, BAG, EACH, etc.                      │
  └──────────────────────┴──────────────────────────────────────────────────────────────────────┘

  I wrote the rewind treating all quantity columns as if they meant the same thing. They don't.

  Proof with T-32206 (Tiger Balm Patch, case pack = 36)

  Today's stock (all DCs): 773,339 patches
  Sales over 3 years, treated as units:     448,083   ← what my rewind used
  Sales over 3 years, actual base units:  6,730,885   ← correct (QUANTITY_adj × QTYBSUOM)
  POs over 3 years, QTY Shipped:          6,160,027   ← already in base units, already correct

  Real flows: out ≈ 6.73M patches, in ≈ 6.16M patches, today = 0.77M.
  → starting inventory was ~1.3M patches (reasonable — POP is a big distributor).

  My rewind saw: out ≈ 0.45M, in ≈ 6.16M, today = 0.77M.
  → "starting inventory was −5M patches" (impossible — negative inventory isn't real).

  So the -3M dip is my bug, not a data problem. Sales look tiny because they're counted in
  "cases-or-whatever-the-customer-bought" instead of individual patches. POs look normal because
  they're already in patches. The two sides don't balance → rewind math drives deep negative to
  compensate.

  How to fix

  Sales: use QUANTITY_adj × QTYBSUOM (which is already per-row correct — each sale row knows its own
  conversion factor). Clean and uses only sales columns, no joins.

  Transfers: messier. The U Of M column is mixed (BOX, BAG, EACH). Two choices:
  - (a) Multiply by Case Pack from item_master. Works for rows where U Of M = CASE/BOX. Needs a lookup.
  - (b) Ignore transfers where U Of M isn't "EACH" and lose some accuracy (how much depends on which
  UOMs dominate; I'd need to count).

  POs: already in base units → no change needed. (I'll verify by spot-checking one PO's Unit Cost × QTY
   Shipped vs Extended Cost.)

  After the fix I'd expect the confidence split to get much better than 188/31. Probably closer to
  200/19 or better.

  Want me to:
  1. Fix sales only (easy, biggest win) and re-run, then assess if transfers still need work?
  2. Fix both at once and just ship it?

  And do you have any prior read on whether transfers are mostly CASE or mixed? If mostly CASE, option
  (a) is fine. If genuinely mixed, I should look.