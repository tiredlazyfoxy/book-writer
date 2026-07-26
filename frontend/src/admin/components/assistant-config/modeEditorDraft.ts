import { makeAutoObservable, runInAction } from "mobx";
import * as assistantConfigApi from "../../../api/assistantConfig";
import { ApiError } from "../../../api/client";
import type { AssistantMode, AssistantTool, SubAgent } from "../../../types/assistantConfig";

/**
 * Component-local draft for the per-mode editor modal — held via
 * `useState(() => new ModeEditorDraft(mode, tools, subAgents))`, so each conditional
 * mount of `ModeEditorModal` builds a fresh one. The split-draft convention
 * (`components/llm-servers/serverFormDraft.ts`): observable fields + pure `get`
 * computeds only, no effectful methods — the submit is the external
 * {@link submitModeEditor} below.
 *
 * `selectedTools` holds **tool names**, `selectedSubAgents` holds **sub-agent ids**
 * (strings — the mode DTO's `sub_agent_ids`). Both are `Set`s and every toggle is a
 * component `onChange` that **reassigns a fresh `Set`** — a `Set` mutated in place is
 * not observable to MobX (`modelsModalDraft.ts:12-13`). Serialization to `string[]`
 * happens only at submit time.
 *
 * `tools` / `subAgents` are the catalogue and the sub-agent list the pickers render
 * (the sub-agent list is how ids become names — `007.context.md`).
 *
 * Skeleton: fields, the constructor signature and the three computeds' shapes are
 * frozen; the seeding from `mode`, the computed bodies and `submitModeEditor` are the
 * coder's.
 */
export class ModeEditorDraft {
  /** The mode's `system_prompt`, `null` seeded as `""`. An empty prompt is valid. */
  systemPrompt = "";
  /** Selected tool **names**. Empty means *no tools*, never "all tools". */
  selectedTools: Set<string>;
  /** Selected sub-agent **ids** (wire strings). */
  selectedSubAgents: Set<string>;

  /** The tool catalogue the picker renders — one `Checkbox` per entry. */
  tools: AssistantTool[];
  /** The sub-agent list the picker renders; `disabled` entries are not offered. */
  subAgents: SubAgent[];

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor(mode: AssistantMode, tools: AssistantTool[], subAgents: SubAgent[]) {
    this.tools = tools;
    this.subAgents = subAgents;
    // Seeded from the mode: a null prompt is an empty string (an empty prompt is a
    // valid stored state), and both selections are fresh `Set`s over the wire arrays.
    this.systemPrompt = mode.system_prompt ?? "";
    this.selectedTools = new Set<string>(mode.tool_names);
    this.selectedSubAgents = new Set<string>(mode.sub_agent_ids);
    makeAutoObservable(this);
  }

  /**
   * Client-side validation, **keyed by WIRE field name**. A mode has **no required
   * field** — an empty prompt and empty selections are all valid (`context.md` →
   * scope decision 1, US-110.AC-4) — so this is normally empty; it exists to keep the
   * draft shape uniform and to hold any future client-side rule.
   */
  get clientErrors(): Record<string, string> {
    // Deliberately empty: nothing on a mode is required, so nothing here may block
    // Save. Any future client-side rule lands here, keyed by wire field name
    // (`system_prompt` / `tool_names` / `sub_agent_ids`).
    return {};
  }

  /** Displayed errors: client validation unioned with (overridden by) server errors. */
  get errors(): Record<string, string> {
    return { ...this.clientErrors, ...this.serverErrors };
  }

  /** True when no submit is in flight and client validation passes. */
  get canSubmit(): boolean {
    return this.submitStatus !== "loading" && Object.keys(this.clientErrors).length === 0;
  }
}

/**
 * Save one mode, in the precedent's exact order (`serverFormDraft.ts:63-118`):
 *
 * clear `draft.serverErrors` + `submitStatus = "loading"` → `assistantConfigApi.saveMode(modeKey, body, signal)`
 * where `body` is `{ system_prompt: draft.systemPrompt || null, tool_names: Array.from(draft.selectedTools), sub_agent_ids: Array.from(draft.selectedSubAgents) }`
 * — an **empty prompt is sent as `null`**, and an empty selection is sent as `[]`
 * (never omitted: empty means *no tools* / *no sub-agents*) → `catch`: on
 * `err instanceof ApiError` write `draft.serverErrors`, set status `"error"` and
 * **return**; otherwise aborted-guard, set status `"error"` and **rethrow** → set
 * status `"ready"` → call `onSaved()`.
 *
 * Status → field mapping (hand-written per modal, the `CreateUserModal.tsx:88-97`
 * precedent): **every** status maps to the **`form`** key — the backend's 400s here
 * (unknown tool, unknown or disabled sub-agent) and its 404 all mean the page's
 * cached catalogue / sub-agent list is stale, which is a whole-form condition, not a
 * field one. `form` renders as an `<Alert color="red">` at the modal top
 * (`ServerFormModal.tsx:56`).
 */
export async function submitModeEditor(
  draft: ModeEditorDraft,
  modeKey: string,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    await assistantConfigApi.saveMode(
      modeKey,
      {
        // An empty prompt is stored as `null`; an empty selection is sent as `[]`,
        // never omitted — empty means *no tools* / *no sub-agents*.
        system_prompt: draft.systemPrompt || null,
        tool_names: Array.from(draft.selectedTools),
        sub_agent_ids: Array.from(draft.selectedSubAgents),
      },
      signal,
    );
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        // Every status maps to the single `form` key — 400 (unknown tool, unknown or
        // disabled sub-agent), 404 (the mode is gone) and anything else all mean the
        // page's cached catalogue / sub-agent list is stale, a whole-form condition.
        draft.serverErrors = { form: err.message || "Could not save the mode." };
        draft.submitStatus = "error";
      });
      return;
    }
    if (signal?.aborted) return;
    runInAction(() => {
      draft.submitStatus = "error";
    });
    throw err;
  }

  runInAction(() => {
    draft.submitStatus = "ready";
  });
  onSaved();
}
