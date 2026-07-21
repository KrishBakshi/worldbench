"use client";

import { useState } from "react";

/**
 * Mobile-only badge pinned to the bottom, suggesting desktop for the full
 * experience. Hidden at md+ via CSS. The close button dismisses it for the
 * session — the layout persists across client navigations, so it stays gone
 * until a full reload rather than being permanently silenced.
 */
export default function MobileNotice() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  function dismiss() {
    setVisible(false);
  }

  return (
    <div className="fixed inset-x-3 bottom-5 z-40 flex justify-center md:hidden">
      <div className="animate-notice flex items-start gap-3 rounded-lg border border-mist/25 bg-void-deep/95 px-4 py-3 shadow-xl backdrop-blur">
        <div className="space-y-0.5">
          <p className="text-xs font-semibold tracking-wide text-mist-bright">
            Best experienced on desktop
          </p>
          <p className="text-[11px] leading-snug text-mist">
            You&apos;re on mobile. Switch to a desktop for the full experience.
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss"
          className="-mr-1 shrink-0 text-mist transition-colors hover:text-mist-bright"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4"
            aria-hidden="true"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  );
}
