# Fast feature 011 — tools-path-reasoning — intended doc changes

Applied by the architect at finalization. **The feature itself edits no file under `docs/architecture/` and none under `docs/product/`.**

The through-line: `llm-client v0.1.5` reads `reasoning_content` and streams it through `on_delta` wrapped in `<think>` / `</think>`. The documented claim that out-of-band reasoning is unrecoverable inside BookWriter is now **false**, and the `--reasoning-format none` deployment requirement is no longer unavoidable — it becomes **one of two working configurations**.

---

## `docs/architecture/backend/features.md`

**Section:** "Deployment requirement — llama.cpp must run with `--reasoning-format none`" (the file's opening section, `**Realizes:** FEAT-013 (operational constraint)`).

**Intended change:** rewrite. The requirement is **softened from mandatory to one of two working shapes**. Two specific sentences are now wrong and must go: that `--reasoning-format none` is "not a preference; it is the only shape BookWriter can consume", and that reasoning sent out-of-band "reaches neither the `on_delta` callback, nor the call's return value, nor the trace — there is no place in BookWriter's code where it could be recovered." Replace with: from `llm-client v0.1.5`, `_stream_openai_tools_response` reads `delta["reasoning_content"]` and streams it through `on_delta` wrapped in `<think>` / `</think>` under a per-round `in_reasoning` state machine, so **structured out-of-band reasoning now works too**. Keep the section — the operational guidance is still worth carrying — but reframed: either configuration delivers thinking, and the silent-degradation failure mode now applies only to a server pinned below `v0.1.5`. Retain the note that BookWriter splits the tags itself in `services/chat_turn.py`'s `ThinkSplitter`, and add **why it needed no change**: v0.1.5 emits the same tags inline into the same text stream the splitter was already built for.

**Reason:** the section's central factual claim was invalidated by the dependency release this feature consumes. Left as-is it would instruct operators to treat a removable constraint as a hard one.

**Section:** the same file's record set (wherever the as-shipped chat-turn behaviour is described).

**Intended change:** record that `build_sampling_options` now forwards `enable_thinking` to `openai`-backend servers, and only that — a **narrow, deliberate partial reversal of feature `011.chat-panel`'s decision 4 / DoD-6**. The original gate's reasoning is **preserved**: llama.cpp-specific params (`top_k`, `repeat_penalty`, `min_p`) still do not belong on an OpenAI endpoint. `enable_thinking` crosses alone because it is the one param in the set the OpenAI path genuinely supports — the `llm` library maps it to `reasoning_effort` for OpenAI models. A `llama-swap` server still receives the full dump, unchanged.

**Reason:** the shipped behaviour of a documented decision changed; the decision history must show the reversal is scoped to one param, or a later reader will read it as the whole gate being abandoned.

---

## `docs/architecture/backend.md`

**Section:** "LLM client", line 104 — the bolded "**Deployment requirement — llama.cpp must run with `--reasoning-format none`**" paragraph.

**Intended change:** rewrite to match the softened `backend/features.md` section. The clause "the streaming tool loop in `llm-client` never reads `reasoning_content`, so out-of-band reasoning is discarded inside the library" is now false for `v0.1.5` and must be corrected; the silent-degradation warning survives, but scoped to a server running without the flag **on a pre-`v0.1.5` client**. Keep the pointer to `backend/features.md` → "Deployment requirement".

**Reason:** mirror of the primary statement; leaving it stale would contradict the file it points at.

**Section:** the dependency listing, line 98 — "The `llm-client` entry is a **shared external library** — keep the git URL and `@v0.1.4` tag verbatim."

**Intended change:** `@v0.1.4` → `@v0.1.5`. This is a fourth mirror of the pin, easy to miss, and the sentence instructs readers to keep the tag *verbatim* — so a stale value here actively invites reverting the bump.

**Reason:** the doc pins a version the code no longer uses, with an explicit instruction not to change it.

---

## `docs/architecture/system-overview.md`

**Section:** the streaming-turn walkthrough, line 166 — the "**Deployment requirement:**" paragraph closing the section.

**Intended change:** soften identically — thinking is no longer visible *only* with `--reasoning-format none`; from `llm-client v0.1.5`, out-of-band `reasoning_content` is consumed too. Keep the pointer to `backend/features.md`. The seven-frame vocabulary above it (item 4) is **unchanged by this feature** — do not touch it.

**Reason:** mirror; it is the statement a newcomer reads first, so a stale copy here has the widest blast radius.

---

## `docs/architecture/quick-reference.md`

**Section:** the SSE frame table's trailing note, line 107 — "Note the deployment requirement in `backend/features.md` — llama.cpp must run with `--reasoning-format none` or thinking is silently lost."

**Intended change:** reword to "one of two supported configurations" and keep the cross-reference. One line.

**Reason:** mirror; the frame table itself needs no change.

---

## Decision reversal to record — feature `024.chat-agent-loop`, D3

**Target:** wherever decision history for the assistant runtime lives (`backend/features.md`'s deployment-requirement section is the natural anchor; the plan folder `docs/plans/024.chat-agent-loop/plan.md:353-358` and its Risk entry at `:404-407` are the source, and plan folders are historical records — **do not edit them**).

**Intended change:** note that **`024`'s decision D3 is reversed**. D3 considered patching the `llm` dependency (~10 LoC) to read `reasoning_content`, **rejected** it, and accepted the limitation as `[manual/live]`, "not claimed as delivered". The patch happened after all — upstream, in `llm-client v0.1.5` (tag on `github.com/Iezious/PythonLLMClient`, commit `7c27d6b`) — and the accepted limitation is **retired**.

**Reason:** a rejected option that later became the solution is exactly the kind of decision history that misleads when left unannotated; a reader hitting D3 must be able to see it no longer holds.

---

## Surfaced follow-up for `/product-spec` (note only — not a doc change here)

No `FEAT`/`UC`/`US`/`AC` in `docs/product/` mandates streamed collapsible assistant thinking. It entered the system through feature `011.chat-panel`'s `context.md` decisions 7/8, not through a requirement; FEAT-013 owns the area, and the `--reasoning-format none` rule is recorded under it as an *operational constraint* rather than an acceptance criterion. An AC for "thinking streams into a collapsible block in the chat pane" may be warranted now that the capability genuinely works on both server shapes.

**This is a surfacing, not an instruction.** `docs/product/` is read-only from architecture and from this feature; only `/product-spec` may add the id. **Do not invent or cite a UC/US id for the thinking display in the meantime.**

## Observations

_populated by the coder_

---
Status: Applied 2026-09-18
Applied items: 7 (all items above that asked for a doc change: the two `backend/features.md` sections, the two `backend.md` edits, `system-overview.md`, `quick-reference.md`, and the `024` D3 reversal)
Rejected items: 0

Notes:

- The `/product-spec` follow-up was applied as a **surfacing only**, as written — no doc change, and no UC/US id invented or cited for the thinking display.
- **Four further edits were added at finalization, beyond this file's list**, all user-approved, all in `docs/architecture/`:
  - **(I)** `assistant-runtime.md` — the "Sampling emission is backend-conditional" bullet was **false** after this feature (it described `build_sampling_options` as sending nothing to an `openai` server). Rewritten to the two-arm rule, `fast/011.tools-path-reasoning` named as its origin.
  - **(J)** `assistant-runtime.md` — the heading "Two `llm-client` v0.1.4 constraints…" → **v0.1.5**. Both constraints still hold; only the version moved.
  - **(K)** `assistant-runtime.md` — the constraint-(a) bullet was **deliberately left unchanged** (minimal edit, user's call): no note added about what v0.1.5 did or did not patch.
  - **(L)** `quick-reference.md` — the `ChatSamplingParams` row's version string → **v0.1.5**; the `top_k` / `repeat_penalty` / `min_p` claim itself is still true and was kept.
- Two adjacent coherence edits were needed for item D to not self-contradict and are recorded in the hand-back: the `pyproject.toml` snippet in `backend.md` (the same pin, quoted verbatim two lines above) and the `backend/features.md` entry in `backend.md`'s document index (which labelled the section by the `--reasoning-format none` flag).
