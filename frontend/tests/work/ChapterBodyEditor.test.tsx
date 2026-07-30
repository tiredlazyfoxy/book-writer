/**
 * The chapter body editor — 015.chapter-writing-free-mode / 005.chapter-body-editor,
 * DoD-2 · DoD-3 · DoD-4.
 *
 * DoD-1 (the pinned TipTap major + `npm run build`), DoD-5 (the Markdown round-trip),
 * DoD-6 (the selection callbacks), DoD-7 (theme inheritance) and DoD-8
 * (`npm run test:types`) are `[manual/live]` and have NO test here. That is not an
 * omission: `005.context.md` -> "jsdom and ProseMirror" fixes it. ProseMirror needs
 * DOM APIs jsdom does not implement (`Range.getClientRects`, real layout rectangles,
 * `document.elementFromPoint`); mounting usually works, typing and selection do not.
 * Faking editor internals to assert an emitted Markdown string would test the test —
 * the same reasoning 014 used for `@dnd-kit`'s drag gesture — so the emitted Markdown,
 * the typing path and the selection path are covered live, not pretended at here.
 *
 * Bound to the frozen seam in status.md -> `## Skeleton` (step 005) — exactly four
 * props, in declaration order, and nothing else:
 *   interface ChapterBodyEditorProps {
 *     initialMarkdown: string;                            // read ONCE at mount (D15)
 *     onChange: (markdown: string) => void;               // Markdown, never HTML/JSON
 *     onSelectionChange: (selectedText: string) => void;  // "" for an empty selection
 *     ariaLabel: string;                                  // the editable region's name
 *   }
 *   const ChapterBodyEditor: React.FunctionComponent<ChapterBodyEditorProps>
 *
 * Every expected value comes from the step file's DoD, never from the component:
 *   - the component mounts and exposes an editable region reachable by its ACCESSIBLE
 *     LABEL, carrying the initial Markdown's RENDERED content (so the heading text is
 *     there and the `#` / `-` markers are not) — DoD-2;
 *   - the formatting toolbar renders its controls WITH accessible names, so a later
 *     surface (006 / 007 / 012) can assert against them by role — DoD-3. The step
 *     says "a small formatting toolbar" and names no individual control, so nothing
 *     here pins WHICH controls exist: the asserted contract is that every control is
 *     a button and every button has a non-empty accessible name. An icon-only toolbar
 *     with no accessible names is exactly the failure this guards.
 *   - the component is a LEAF: no HTTP, no state beyond the editor instance, so
 *     mounting it with stub callbacks triggers neither a request nor a change
 *     emission — DoD-4. The skeleton flagged this as the vacuous-pass risk (a
 *     component that throws makes no network call either), so the mount is asserted
 *     FIRST and the absence only afterwards.
 *
 * Queries are by ROLE or LABEL only — no test ids, nothing asserted about colour.
 * Nothing is mocked: the component imports no `api/` module, so a whole-module mock
 * would prove nothing here; DoD-4 is carried by the real `fetch` / `XMLHttpRequest`
 * spies below plus the mount assertion in front of them.
 *
 * `globals: false`: every primitive is imported explicitly. `tests/setup.ts` supplies
 * `matchMedia` / `ResizeObserver` / `scrollIntoView` and runs `cleanup()`; the two
 * ProseMirror-only stubs live HERE, at the top of this file, because
 * `frontend/tests/support/` and `vitest.config.ts` are in NO step's file list.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../support/render";
import {
  ChapterBodyEditor,
  type ChapterBodyEditorProps,
} from "../../src/work/components/chapter/ChapterBodyEditor";

// --------------------------------------------------------------------------
// jsdom stubs — the minimum ProseMirror needs to MOUNT. Nothing here fakes an
// editor internal; these are DOM geometry APIs jsdom simply does not implement.
// --------------------------------------------------------------------------

interface MutablePrototype {
  [key: string]: unknown;
}

const emptyRect = (): DOMRect =>
  ({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: 0,
    height: 0,
    toJSON: () => ({}),
  }) as DOMRect;

const emptyRectList = (): DOMRectList => {
  const list = {
    length: 0,
    item: () => null,
    [Symbol.iterator]: function* (): Generator<DOMRect> {},
  };
  return list as unknown as DOMRectList;
};

const rangeProto = Range.prototype as unknown as MutablePrototype;
if (typeof rangeProto["getClientRects"] !== "function") {
  rangeProto["getClientRects"] = emptyRectList;
}
if (typeof rangeProto["getBoundingClientRect"] !== "function") {
  rangeProto["getBoundingClientRect"] = emptyRect;
}

// jsdom's `elementFromPoint` is unimplemented; ProseMirror probes it in places.
Object.defineProperty(document, "elementFromPoint", {
  writable: true,
  configurable: true,
  value: () => null,
});

// --------------------------------------------------------------------------
// Fixtures
// --------------------------------------------------------------------------

/** The accessible name the page will pass; the ONLY handle the specs use. */
const EDITOR_LABEL = "Chapter body";

/**
 * A body exercising three Markdown constructs, so "rendered content" is
 * distinguishable from "raw Markdown": a heading, a paragraph and a list.
 */
const BODY_MARKDOWN = [
  "# The lighthouse",
  "",
  "Keeper Maren trimmed the wick before the fog came in.",
  "",
  "- salt",
  "- rope",
  "",
].join("\n");

const HEADING_TEXT = "The lighthouse";
const PARAGRAPH_TEXT = "Keeper Maren trimmed the wick before the fog came in.";
const LIST_ITEM_TEXT = "salt";

interface RenderedEditor {
  onChange: ReturnType<typeof vi.fn>;
  onSelectionChange: ReturnType<typeof vi.fn>;
  unmount: () => void;
}

function renderEditor(overrides: Partial<ChapterBodyEditorProps> = {}): RenderedEditor {
  const onChange = vi.fn();
  const onSelectionChange = vi.fn();
  const props: ChapterBodyEditorProps = {
    initialMarkdown: BODY_MARKDOWN,
    onChange,
    onSelectionChange,
    ariaLabel: EDITOR_LABEL,
    ...overrides,
  };
  const { unmount } = renderWithProviders(<ChapterBodyEditor {...props} />);
  return { onChange, onSelectionChange, unmount };
}

/**
 * The editable region, reached by its accessible label and by nothing else —
 * DoD-2's own wording. `findAll` (not `get`) so the editor may legitimately
 * arrive on its library hook's own tick, and so a wrapper that repeats the
 * label fails on an assertion rather than on a query throw.
 */
async function findEditableRegion(): Promise<HTMLElement> {
  const labelled = await screen.findAllByLabelText(EDITOR_LABEL);
  expect(labelled.length).toBeGreaterThanOrEqual(1);
  return labelled[labelled.length - 1] as HTMLElement;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

// --------------------------------------------------------------------------
// DoD-2 — mounts, and the editable region is reachable by its accessible label
// --------------------------------------------------------------------------

describe("ChapterBodyEditor — the editable region", () => {
  it("exposes an editable region reachable by the accessible label it was given__DoD2", async () => {
    renderEditor();

    const region = await findEditableRegion();

    expect(region).toBeInTheDocument();
  });

  it("names the editable region with the ariaLabel prop, not a fixed string__DoD2", async () => {
    // The label is a PROP: a second surface mounting a second editor must be able
    // to give it its own name. Nothing may hard-code "Chapter body".
    renderEditor({ ariaLabel: "Draft of chapter two" });

    const labelled = await screen.findAllByLabelText("Draft of chapter two");

    expect(labelled.length).toBeGreaterThanOrEqual(1);
    expect(screen.queryAllByLabelText(EDITOR_LABEL)).toHaveLength(0);
  });

  it("shows the initial Markdown's RENDERED content inside that region__DoD2", async () => {
    renderEditor();

    const region = await findEditableRegion();
    const text = region.textContent ?? "";

    expect(text).toContain(HEADING_TEXT);
    expect(text).toContain(PARAGRAPH_TEXT);
    expect(text).toContain(LIST_ITEM_TEXT);
    // Rendered, not raw: the Markdown syntax markers are consumed by the parse.
    expect(text).not.toContain(`# ${HEADING_TEXT}`);
    expect(text).not.toContain(`- ${LIST_ITEM_TEXT}`);
  });

  it("still exposes the labelled editable region for an empty body__DoD2", async () => {
    // `""` is a legitimate chapter body (the wire contract says so explicitly), so
    // an empty initial Markdown must still mount an editable, reachable region.
    renderEditor({ initialMarkdown: "" });

    const region = await findEditableRegion();

    expect(region).toBeInTheDocument();
    expect(region.textContent ?? "").not.toContain(HEADING_TEXT);
  });
});

// --------------------------------------------------------------------------
// DoD-3 — the formatting toolbar's controls carry accessible names
// --------------------------------------------------------------------------

describe("ChapterBodyEditor — the formatting toolbar", () => {
  it("renders its formatting controls as buttons that all carry an accessible name__DoD3", async () => {
    renderEditor();
    await findEditableRegion();

    const controls = screen.getAllByRole("button");
    // "A small formatting toolbar" — more than one control, and the step names
    // none of them, so nothing here asserts WHICH.
    expect(controls.length).toBeGreaterThanOrEqual(2);

    // Every one of them is assertable by role + name: an icon-only control with no
    // accessible name would be invisible to 006 / 007 / 012 and to a screen reader.
    const named = screen.queryAllByRole("button", { name: /\S/ });
    expect(named).toHaveLength(controls.length);
  });

  it("renders those named controls for an empty body too__DoD3", async () => {
    renderEditor({ initialMarkdown: "" });
    await findEditableRegion();

    const controls = screen.getAllByRole("button");
    expect(controls.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryAllByRole("button", { name: /\S/ })).toHaveLength(controls.length);
  });
});

// --------------------------------------------------------------------------
// DoD-4 — a leaf: no network call, no state beyond the editor instance
// --------------------------------------------------------------------------

describe("ChapterBodyEditor — the leaf contract", () => {
  it("mounts successfully and only THEN: no request, no change emission__DoD4", async () => {
    const fetchSpy = vi.fn(() => Promise.reject(new Error("no network in this component")));
    vi.stubGlobal("fetch", fetchSpy);
    const xhrOpenSpy = vi
      .spyOn(XMLHttpRequest.prototype, "open")
      .mockImplementation(() => undefined);

    const { onChange, unmount } = renderEditor();

    // ORDER IS LOAD-BEARING. A component that throws on render makes no network
    // call either, so the absence below proves nothing unless the mount is proved
    // first — the skeleton flagged this item as the vacuous-pass risk.
    const region = await findEditableRegion();
    expect(region).toBeInTheDocument();
    expect(region.textContent ?? "").toContain(PARAGRAPH_TEXT);

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(xhrOpenSpy).not.toHaveBeenCalled();
    // Mounting is not an edit: the initial Markdown is READ, never echoed back.
    expect(onChange).not.toHaveBeenCalled();

    // Nothing is persisted or flushed on the way out either.
    unmount();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(xhrOpenSpy).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("makes no request for an empty body either, and emits no change__DoD4", async () => {
    const fetchSpy = vi.fn(() => Promise.reject(new Error("no network in this component")));
    vi.stubGlobal("fetch", fetchSpy);
    const xhrOpenSpy = vi
      .spyOn(XMLHttpRequest.prototype, "open")
      .mockImplementation(() => undefined);

    const { onChange } = renderEditor({ initialMarkdown: "" });

    const region = await findEditableRegion();
    expect(region).toBeInTheDocument();

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(xhrOpenSpy).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });
});
