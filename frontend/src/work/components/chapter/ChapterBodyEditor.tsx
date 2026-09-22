import { observer } from "mobx-react-lite";
import type { ReactElement } from "react";
import { RichTextEditor } from "@mantine/tiptap";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import { Markdown } from "tiptap-markdown";
import type { MarkdownStorage } from "tiptap-markdown";
// The widget's OWN stylesheet, imported HERE and deliberately not from `work/main.tsx`
// (step 005 Interface intent): the style then ships with the only bundle that uses it and
// no entry file enters this feature's scope. Part of the freeze — do not move it.
// `frontend.md`'s "no CSS modules / no styled-components / no Tailwind" rule is about
// authored styling; a vendored stylesheet from the library that owns the widget is none of
// those, and `outcome.md` records the addition so it is sanctioned rather than drift.
import "@mantine/tiptap/styles.css";

/**
 * Props of {@link ChapterBodyEditor}. **FROZEN (skeleton 015/005).**
 *
 * These four are the seam steps **006, 007 and 012 mock** — those specs substitute this
 * whole module with a trivial stub that renders a labelled control and calls `onChange` /
 * `onSelectionChange` (`context.md` → "The one testing decision this feature has to
 * make"). Adding a prop later is cheap; **changing the meaning of one of these four is
 * not** — three specs bind to them.
 *
 * What is deliberately ABSENT, and must stay absent:
 * - **no `editable` / read-only flag** — a `planned` / `closing` / `closed` body renders
 *   through `react-markdown` on the page (D16); this component is mounted only when the
 *   chapter is `open`;
 * - **no `ref` and no imperative `setContent`** — external draft writes re-sync by
 *   **remount** (D15): the page keys this component on a counter it bumps on every
 *   external write (assistant canvas frame, undo pop, buffer restore, reconciliation
 *   choice), so TipTap re-initializes from the new content;
 * - **no page state, no book/chapter id, no save concern, no HTTP.** This is a leaf: it
 *   knows nothing about chapters, books, saving or the assistant.
 */
export interface ChapterBodyEditorProps {
  /**
   * The Markdown the document is built from — read **ONCE, at mount** (D15). The
   * component never watches this prop for changes and must not: a later value only
   * reaches the document because the page remounted the component under a new key.
   */
  initialMarkdown: string;
  /**
   * Called whenever the author edits, with the document serialized back to **Markdown** —
   * never HTML, never ProseMirror JSON. The page stores Markdown and the server stores
   * Markdown (D2), so this string is what a save eventually puts on the wire.
   */
  onChange: (markdown: string) => void;
  /**
   * Called whenever the selection moves, with the **plain text** of the current selection.
   * An empty selection (a collapsed caret, or a cleared selection) is expressed as the
   * **empty string `""`** — the callback still fires, it is not skipped. This is what
   * feeds D5: the page holds the selection client-side only and sends its text as a flat
   * field on the turn request; nothing about a selection is ever persisted.
   */
  onSelectionChange: (selectedText: string) => void;
  /**
   * The accessible name of the **editable region** — so it is reachable by role/label in
   * tests and by a screen reader in life. Queries in this project are by role or label
   * only, never by test-id; an unlabelled editor is untestable here.
   */
  ariaLabel: string;
}

/**
 * The chapter body editor — Mantine's `RichTextEditor` over a TipTap/ProseMirror document
 * whose content is **Markdown in and Markdown out** (D3, D2). One `observer` component,
 * and nothing else in this file.
 *
 * **What it must be when implemented** (the contract the freeze fixes; no behavior is
 * implemented here):
 *
 * - a TipTap instance built with the library's own `useEditor` from `@tiptap/react`.
 *   Consuming a library hook is **not** a breach of the no-custom-`useX` rule — the rule
 *   forbids AUTHORING hooks; 014 recorded the same reading for `@dnd-kit`'s `useSortable`;
 * - extensions: the starter set (`StarterKit` from `@tiptap/starter-kit`) plus the
 *   Markdown extension (`Markdown` from `tiptap-markdown`); `Link` from
 *   `@tiptap/extension-link` is `@mantine/tiptap`'s declared peer and is what a link
 *   control needs;
 * - `content` initialized from {@link ChapterBodyEditorProps.initialMarkdown} **once**;
 * - `onUpdate` → `onChange` with the document serialized as Markdown
 *   (`editor.storage.markdown` cast to `tiptap-markdown`'s `MarkdownStorage`, then
 *   `.getMarkdown()` — the package declares no global augmentation of `Editor.storage`,
 *   so the cast is how this stays free of `any`);
 * - `onSelectionUpdate` → `onSelectionChange` with the selected plain text, `""` when the
 *   selection is empty;
 * - the editable region carries {@link ChapterBodyEditorProps.ariaLabel} as its accessible
 *   name (TipTap's `editorProps.attributes`, which is where the ProseMirror-owned DOM node
 *   takes attributes from — verified to typecheck against the pinned major);
 * - a small formatting toolbar built from **Mantine's own control components**
 *   (`RichTextEditor.Toolbar` / `.ControlsGroup` / `.Bold` / `.Italic` / …), which carry
 *   their own accessible names, so a later surface can assert against them by role.
 *
 * **Hard rules, all of them part of the freeze.** `observer`. **No `useEffect`** — not
 * even a prop-watching one (D15). No `useState`, no custom `useX` hook of ours, no
 * `useCallback` / `useMemo` / `useReducer`, no React context, no Mantine `useForm`. No
 * HTTP and no `api/` import. No local styling beyond the library's own stylesheet
 * imported above — no CSS module, no styled-component, no Tailwind, no inline theme
 * override; the editor inherits the app theme (dark by default) from `MantineProvider`.
 */
export const ChapterBodyEditor = observer(function ChapterBodyEditor({
  initialMarkdown,
  onChange,
  onSelectionChange,
  ariaLabel,
}: ChapterBodyEditorProps): ReactElement {
  // The library's OWN hook — consuming one is not a breach of the no-custom-`useX` rule.
  // No dependency list is passed, so the instance is created once at mount and
  // `initialMarkdown` is read exactly once (D15); a later value reaches the document only
  // because the page remounted this component under a new key. `immediatelyRender` keeps
  // the document present on the very first render rather than after a tick.
  const editor = useEditor({
    immediatelyRender: true,
    extensions: [StarterKit, Link, Markdown],
    content: initialMarkdown,
    editorProps: {
      // The editable node is ProseMirror's, so its accessible name has to be handed down
      // here — this is what makes the region reachable by role/label.
      attributes: { role: "textbox", "aria-label": ariaLabel },
    },
    onUpdate: ({ editor: edited }) => {
      // Markdown out — never HTML, never ProseMirror JSON. `tiptap-markdown` declares no
      // global augmentation of `Editor.storage`, so the cast is how this stays `any`-free.
      onChange((edited.storage.markdown as MarkdownStorage).getMarkdown());
    },
    onSelectionUpdate: ({ editor: selected }) => {
      const { from, to, empty } = selected.state.selection;
      // An empty selection is the empty string, and the callback still fires.
      onSelectionChange(empty ? "" : selected.state.doc.textBetween(from, to, "\n"));
    },
  });

  return (
    <RichTextEditor editor={editor}>
      <RichTextEditor.Toolbar>
        <RichTextEditor.ControlsGroup>
          <RichTextEditor.Bold />
          <RichTextEditor.Italic />
        </RichTextEditor.ControlsGroup>
        <RichTextEditor.ControlsGroup>
          <RichTextEditor.H2 />
          <RichTextEditor.BulletList />
        </RichTextEditor.ControlsGroup>
      </RichTextEditor.Toolbar>

      <RichTextEditor.Content />
    </RichTextEditor>
  );
});
