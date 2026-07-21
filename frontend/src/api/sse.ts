import { authHeaders } from "./client";

/**
 * Typed callbacks for a streamed SSE response. Generic (non-domain) seed for the
 * scaffold — resource-specific frame shapes arrive with their feature.
 */
export interface SSEHandlers {
  /** One parsed frame: the `event:` name and the JSON-parsed `data:` payload. */
  onEvent?: (event: string, data: unknown) => void;
  /** Transport/parse failure or a server `error` frame. */
  onError?: (message: string) => void;
  /** Stream completed normally. */
  onDone?: () => void;
}

/**
 * POST a JSON body and stream the response as server-sent events — a hand-rolled
 * `fetch` reader (NOT `EventSource`): sends `authHeaders()`, reads
 * `res.body.getReader()` through a `TextDecoder`, splits on "\n\n", parses
 * `event:` / `data:` lines per frame, dispatches to `handlers`, swallows `AbortError`.
 * Returns an `AbortController` the caller can use to cancel the stream.
 */
export function streamPost(
  url: string,
  body: object,
  handlers: SSEHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = (await res.json().catch(() => null)) as { detail?: string } | null;
        handlers.onError?.(err?.detail ?? res.statusText);
        return;
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split on double-newline (SSE event boundary); keep the trailing partial frame.
        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;

        for (const part of parts) {
          if (!part.trim()) continue;

          let eventType = "message";
          let data = "";
          for (const line of part.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              data = line.slice(6);
            }
          }
          if (!data) continue;

          const parsed: unknown = JSON.parse(data);

          if (eventType === "error") {
            const message =
              parsed && typeof parsed === "object" && "message" in parsed &&
              typeof (parsed as { message: unknown }).message === "string"
                ? (parsed as { message: string }).message
                : "Stream error";
            handlers.onError?.(message);
          } else if (eventType === "done") {
            handlers.onDone?.();
          } else {
            handlers.onEvent?.(eventType, parsed);
          }
        }
      }
    } catch (err) {
      if ((err as DOMException).name !== "AbortError") {
        handlers.onError?.(err instanceof Error ? err.message : "Stream failed");
      }
    }
  })();

  return controller;
}
