# fast/002.admin-ui-retune — Admin SPA nav retune
<!-- roadmap:start -->
- **Stage:** 2.data-foundation · **Track:** fast · **Size:** S
- **Depends on:** `005.user-management`

## Definition
Retune the admin SPA's shell so its navigation is coherent: fix the left
menu, wire user logout, and add a "switch to main site" path back to the
user SPA. Corrects existing errors in the delivered admin platform
(FEAT-001..005 surfaces); adds no new domain behaviour.

## Scope
**In:** admin left-menu fixes; logout action; a link/redirect from admin to
the main (user) SPA; the specific errors enumerated at planning.
**Out:** any book-domain feature; new admin capabilities beyond nav/logout.

## Open questions for the planner
- The concrete errors are detailed at planning ("details on planning"). If
  they turn out cross-cutting (more than a single UI-nav pass, >300 LoC),
  promote to `/planner` — this is booked fast on the expectation it is a
  cohesive nav/logout retune.
<!-- roadmap:end -->
