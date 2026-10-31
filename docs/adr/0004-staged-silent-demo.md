# 0004. Stage the silent-change demo so it is repeatable

Date: 2026-10-21. Status: Accepted (demo only).

## Context
In rehearsal, Silent on Inventory sometimes ended in hold or in a promotion instead of the
operator question. The outcome depended on where the replay was when the button was pressed: some
stretches of real SMD data are not learnable by a challenger fitted on half a day, and the drift
detector's delay moved the start of the evidence window.

## Decision
For services in `fleet.DEMO_SILENT_CURSOR` (Inventory), Silent continues the replay from a verified
stretch, uses a fixed seed for the injected change, and opens the quarantine at the click
(`request_validity_check(restart=True)`), restarting one already in progress.

## Alternatives considered
Weaker or mirrored injections, other services, and relaxing the learnability test. None reached
the question reliably, and relaxing the test would weaken the safety margin.

## Consequences
24/24 clicks reach the question after exactly 1,440 events. Only the demo controls change; the
algorithm and every evaluated result are untouched. On stage the quarantine is opened by the click,
not by the drift detector, which must be said if asked.
