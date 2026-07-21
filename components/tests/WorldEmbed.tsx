"use client";

import { useEffect, useRef, useState } from "react";

function ExpandIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="15 3 21 3 21 9" />
      <polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" />
      <line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

export default function WorldEmbed({ src }: { src: string }) {
  const [expanded, setExpanded] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!expanded) return;

    document.body.style.overflow = "hidden";

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setExpanded(false);
    }
    window.addEventListener("keydown", onKeyDown);

    // Once the user clicks into the 3D world, keyboard focus is inside the
    // iframe and Escape fires on its document, not ours — so the window listener
    // alone misses it. world.html is same-origin, so also listen in there. The
    // load handler re-attaches if the frame reloads; try/catch guards the rare
    // case the document isn't reachable.
    const iframe = iframeRef.current;
    let innerWindow: Window | null = null;

    function attachToFrame() {
      try {
        innerWindow?.removeEventListener("keydown", onKeyDown);
        innerWindow = iframe?.contentWindow ?? null;
        innerWindow?.addEventListener("keydown", onKeyDown);
      } catch {
        innerWindow = null;
      }
    }

    attachToFrame();
    iframe?.addEventListener("load", attachToFrame);

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKeyDown);
      iframe?.removeEventListener("load", attachToFrame);
      try {
        innerWindow?.removeEventListener("keydown", onKeyDown);
      } catch {
        // frame already gone; nothing to detach
      }
    };
  }, [expanded]);

  return (
    <div
      // Expanded: a dimmed backdrop that closes on click. Collapsed: the inline
      // frame. The dialog inside stops the click from bubbling to the backdrop.
      onClick={expanded ? () => setExpanded(false) : undefined}
      className={
        expanded
          ? "animate-backdrop-fade fixed inset-0 z-50 flex items-center justify-center bg-void/20 p-4 backdrop-blur-sm sm:p-8"
          : "relative mx-auto aspect-video w-full max-w-3xl overflow-hidden rounded-lg border border-line"
      }
    >
      <div
        onClick={expanded ? (e) => e.stopPropagation() : undefined}
        className={
          expanded
            ? "animate-modal-pop relative flex h-[70vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-line bg-void shadow-2xl sm:w-[70vw]"
            : "relative flex h-full w-full flex-col"
        }
      >
        <iframe
          ref={iframeRef}
          src={src}
          title="world.html"
          className="w-full flex-1"
          loading="lazy"
          sandbox="allow-scripts allow-same-origin"
        />

        {expanded && (
          <div className="flex shrink-0 items-center justify-end border-t border-line px-4 py-2.5">
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.15em] text-mist transition-colors hover:text-mist-bright"
            >
              Open in dedicated window
              <ExternalLinkIcon />
            </a>
          </div>
        )}

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "Close" : "Enlarge"}
          className="absolute top-3 right-3 flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-void-deep/80 text-mist backdrop-blur transition-colors hover:text-mist-bright"
        >
          {expanded ? <CloseIcon /> : <ExpandIcon />}
        </button>
      </div>
    </div>
  );
}
