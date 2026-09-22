import { makeAutoObservable, runInAction } from "mobx";
import * as assistantConfigApi from "../../../api/assistantConfig";
import { ApiError } from "../../../api/client";
import type { AssistantMode, AssistantTool, SubAgent } from "../../../types/assistantConfig";
import type { LlmServer } from "../../../types/llmServers";

/**
 * One entry of the model `<Select>`'s data — the Mantine `{ value, label }` shape.
 *
 * `value` is an **opaque encoding of the (server id, model name) pair** plus one
 * sentinel for the inherit choice. The encoding is private to this module: it is
 * produced by {@link SubAgentFormDraft.modelOptions} / {@link SubAgentFormDraft.modelValue}
 * and consumed by {@link applyModelOption}, and it **never reaches the wire** — the two
 * wire fields are always `draft.llmServerId` / `draft.modelName`
 * (`008.context.md` → "The model picker's data source").
 */
export interface ModelOption {
  value: string;
  label: string;
}

/**
 * The `<Select>` value standing for *no model assignment*. Module-private, like the
 * pair encoding itself: it is never a server id, never a model name and never reaches
 * the wire — {@link applyModelOption} turns it into `null` + `null`.
 */
const INHERIT_VALUE = "__inherit__";

/** The inherit choice's visible label — the one place it is spelled (US-113.AC-6). */
const INHERIT_LABEL = "Inherit the main chat's model";

/**
 * Encode a `(server id, model name)` pair into one `<Select>` value. The separator is
 * safe because a server id is a numeric snowflake string: the **first** `:` is always
 * the boundary, whatever the model name contains.
 */
function encodeModelValue(serverId: string, modelName: string): string {
  return `${serverId}:${modelName}`;
}

/**
 * Decode a `<Select>` value back into the two wire fields. The inherit sentinel, a
 * `null` (Mantine's clear) and anything malformed all decode to the *inherit* pair —
 * both `null` — so a half-set pair is unreachable from this UI.
 */
function decodeModelValue(value: string | null): {
  llmServerId: string | null;
  modelName: string | null;
} {
  if (value === null || value === INHERIT_VALUE) return { llmServerId: null, modelName: null };
  const separator = value.indexOf(":");
  if (separator <= 0 || separator === value.length - 1) {
    return { llmServerId: null, modelName: null };
  }
  return {
    llmServerId: value.slice(0, separator),
    modelName: value.slice(separator + 1),
  };
}

/**
 * Component-local draft for the create/edit sub-agent form modal — held via
 * `useState(() => new SubAgentFormDraft(subAgent, tools, modes, servers))`, so each
 * conditional mount of `SubAgentFormModal` builds a fresh one. The split-draft
 * convention (`components/llm-servers/serverFormDraft.ts`,
 * `components/assistant-config/modeEditorDraft.ts`): observable fields + pure `get`
 * computeds only, no effectful methods — the two effectful operations are the external
 * {@link applyModelOption} and {@link submitSubAgentForm} below.
 *
 * `subAgent` is **`null` for create** and a row for edit. `selectedTools` holds tool
 * **names**, `selectedModes` holds mode **keys**. Both are `Set`s and every toggle is a
 * component `onChange` that **reassigns a fresh `Set`** — a `Set` mutated in place is
 * not observable to MobX (`modelsModalDraft.ts:12-13`). Serialization to `string[]`
 * happens only at submit time.
 *
 * The model assignment is **two coupled fields**, never one: `llmServerId` + `modelName`
 * both `null` means *inherit the main chat's model* (US-113.AC-6). There is no UI path
 * to a half-set pair — {@link applyModelOption} always writes both.
 *
 * There is deliberately **no `disabled` field**: disable/enable is a row action on the
 * page, because it cascades (detaching from every mode) and a form checkbox would hide
 * that (`008.context.md`). The wire update body carries no `disabled` either.
 */
export class SubAgentFormDraft {
  /** The sub-agent's name. The only client-required field. */
  name = "";
  /** The sub-agent's `system_prompt` (non-nullable on the wire; `""` is valid). */
  systemPrompt = "";
  /** Selected tool **names**. Empty is valid. */
  selectedTools: Set<string>;
  /** Selected accessible-mode **keys**. Empty is valid. */
  selectedModes: Set<string>;
  /** Model assignment, half 1 of 2 — wire `llm_server_id`. `null` with `modelName` null = inherit. */
  llmServerId: string | null = null;
  /** Model assignment, half 2 of 2 — wire `model_name`. Moves with `llmServerId`, always. */
  modelName: string | null = null;

  /** The tool catalogue the picker renders — one `Checkbox` per entry; may be empty. */
  tools: AssistantTool[];
  /** The fixed five modes the accessible-modes picker renders, labelled via `modeLabel`. */
  modes: AssistantMode[];
  /** Every LLM server; only `is_active` ones contribute model options. */
  servers: LlmServer[];

  serverErrors: Record<string, string> = {};
  submitStatus: "idle" | "loading" | "ready" | "error" = "idle";

  constructor(
    subAgent: SubAgent | null,
    tools: AssistantTool[],
    modes: AssistantMode[],
    servers: LlmServer[],
  ) {
    this.tools = tools;
    this.modes = modes;
    this.servers = servers;
    // Seeded from the row on edit; left at the create defaults when `subAgent` is null.
    // Both selections are fresh `Set`s over the wire arrays, and the model pair is
    // copied as a pair — the row can only ever carry both halves or neither.
    if (subAgent) {
      this.name = subAgent.name;
      this.systemPrompt = subAgent.system_prompt;
      this.llmServerId = subAgent.llm_server_id;
      this.modelName = subAgent.model_name;
    }
    this.selectedTools = new Set<string>(subAgent ? subAgent.tool_names : []);
    this.selectedModes = new Set<string>(subAgent ? subAgent.mode_keys : []);
    makeAutoObservable(this);
  }

  /**
   * The model `<Select>`'s data: the **active** servers' `enabled_models` flattened into
   * one selectable entry per (server, model) pair — labelled so both the server name and
   * the model name are visible — **plus** an explicit *"Inherit the main chat's model"*
   * choice whose value is the inherit sentinel (US-113.AC-6). **Inactive servers
   * contribute nothing** (US-113.AC-5); a server with an empty `enabled_models`
   * contributes nothing either. The inherit choice is always present, even with zero
   * servers.
   */
  get modelOptions(): ModelOption[] {
    // The inherit choice is always first and always present — even with zero servers.
    const options: ModelOption[] = [{ value: INHERIT_VALUE, label: INHERIT_LABEL }];
    for (const server of this.servers) {
      // An inactive server contributes nothing: its models are not assignable
      // (US-113.AC-5). A server with no enabled models contributes nothing either.
      if (!server.is_active) continue;
      for (const model of server.enabled_models) {
        options.push({
          // Labelled with BOTH names, so two models on one server — and one model
          // name offered by two servers — stay distinguishable.
          value: encodeModelValue(server.id, model),
          label: `${server.name} / ${model}`,
        });
      }
    }
    return options;
  }

  /**
   * The `<Select>`'s current `value`: the encoding of the draft's `(llmServerId,
   * modelName)` pair, or the inherit sentinel when both are `null` — so an unset
   * assignment shows the inherit choice as the default selection rather than a blank box.
   */
  get modelValue(): string {
    if (this.llmServerId !== null && this.modelName !== null) {
      return encodeModelValue(this.llmServerId, this.modelName);
    }
    return INHERIT_VALUE;
  }

  /**
   * Client-side validation, **keyed by WIRE field name** (`name`, not `subAgentName` —
   * that is what makes the `errors` merge work without a translation table). A
   * blank/whitespace-only `name` produces a `name` error. **Nothing else is required**:
   * an empty prompt, an empty tool set, an empty mode set and the inherit model choice
   * are all valid.
   */
  get clientErrors(): Record<string, string> {
    const e: Record<string, string> = {};
    // The only client-side rule: everything else on this form is optional.
    if (!this.name.trim()) e.name = "Name is required.";
    return e;
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
 * Apply a model `<Select>` change, writing **both** halves of the pair together inside a
 * `runInAction` (US-113.AC-5, US-114.AC-4):
 *
 * - a concrete option value → decode it and set `draft.llmServerId` **and**
 *   `draft.modelName` to that server id and model name;
 * - the inherit sentinel (and `null`, which Mantine sends on clear) → set **both** to
 *   `null`.
 *
 * This is the only writer of the pair, which is why the UI can never emit a half-set
 * assignment; the backend's 400 is a second line of defence, not the first.
 */
export function applyModelOption(draft: SubAgentFormDraft, value: string | null): void {
  const pair = decodeModelValue(value);
  runInAction(() => {
    // Both halves, always, in one action — this is the pair's only writer.
    draft.llmServerId = pair.llmServerId;
    draft.modelName = pair.modelName;
  });
}

/**
 * Save one sub-agent — **`subAgentId === null` means create** — in the precedent's exact
 * order (`serverFormDraft.ts:63-118`, `modeEditorDraft.ts:96-141`):
 *
 * clear `draft.serverErrors` + `submitStatus = "loading"` →
 * `assistantConfigApi.createSubAgent(body, signal)` or
 * `assistantConfigApi.updateSubAgent(subAgentId, body, signal)`, where `body` is
 * `{ name, system_prompt, llm_server_id: draft.llmServerId, model_name: draft.modelName,
 * tool_names: Array.from(draft.selectedTools), mode_keys: Array.from(draft.selectedModes) }`
 * — **both model fields always explicitly present**, `null` + `null` meaning *inherit*
 * (`context.md` → "Writes are full-replace"), and an empty selection sent as `[]`, never
 * omitted → `catch`: on `err instanceof ApiError` write `draft.serverErrors`, set status
 * `"error"` and **return**; otherwise aborted-guard, set status `"error"` and **rethrow**
 * → set status `"ready"` → call `onSaved()`.
 *
 * Status → field mapping (the `CreateUserModal.tsx:88-97` precedent):
 *
 * | Status | Key | Behind it |
 * |---|---|---|
 * | 409 | `name` | the name is already taken (US-113.AC-3) |
 * | 400 | `name` when the message identifies a **blank name**; otherwise `form` | blank-name; else invalid-model-pair / unknown-or-inactive-server / model-not-enabled / unknown-tool / mode-not-found / sub-agent-disabled |
 * | anything else (incl. 404) | `form` | the row was removed or the cached catalogue is stale |
 *
 * A `form` key renders as an `<Alert color="red">` at the modal top
 * (`ServerFormModal.tsx:56`). A refused save must leave the modal open with the admin's
 * input intact and must **not** call `onSaved` (UC-096 exception flow).
 */
export async function submitSubAgentForm(
  draft: SubAgentFormDraft,
  subAgentId: string | null,
  onSaved: () => void,
  signal?: AbortSignal,
): Promise<void> {
  // Both model fields are always explicitly present (`null` + `null` = inherit), and
  // both selections are always sent — `[]` when empty, never omitted (full-replace).
  const body = {
    name: draft.name,
    system_prompt: draft.systemPrompt,
    llm_server_id: draft.llmServerId,
    model_name: draft.modelName,
    tool_names: Array.from(draft.selectedTools),
    mode_keys: Array.from(draft.selectedModes),
  };

  runInAction(() => {
    draft.serverErrors = {};
    draft.submitStatus = "loading";
  });

  try {
    if (subAgentId === null) {
      await assistantConfigApi.createSubAgent(body, signal);
    } else {
      await assistantConfigApi.updateSubAgent(subAgentId, body, signal);
    }
  } catch (err) {
    if (err instanceof ApiError) {
      runInAction(() => {
        // A 400 whose message names a blank name is a field condition; every other
        // 400 (bad model pair, unknown tool, unknown mode, disabled sub-agent) and
        // every other status mean the cached catalogue or the row itself is stale —
        // whole-form conditions.
        const message = err.message;
        const lower = message.toLowerCase();
        const blankName =
          lower.includes("name") &&
          (lower.includes("blank") || lower.includes("empty") || lower.includes("required"));
        draft.serverErrors =
          err.status === 409
            ? { name: message || "That name is already taken." }
            : err.status === 400 && blankName
              ? { name: message || "Name is required." }
              : { form: message || "Could not save the sub-agent." };
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
