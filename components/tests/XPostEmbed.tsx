"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

const WIDGETS_SRC = "https://platform.twitter.com/widgets.js";
/** If the widget hasn't rendered by now, assume it's blocked and show the link. */
const RENDER_TIMEOUT_MS = 4000;

type TwitterWidgets = {
  widgets: { createTweet: (id: string, el: HTMLElement, options?: object) => Promise<unknown> };
};

declare global {
  interface Window {
    twttr?: TwitterWidgets;
  }
}

/**
 * Injected once per page load and shared by every embed on it. Resolves with the
 * global the script installs, or rejects when the request is blocked — extensions
 * and network filters commonly block this host, which is why callers must have a
 * fallback rather than treating success as guaranteed.
 */
let widgetsPromise: Promise<TwitterWidgets> | null = null;

function loadWidgets(): Promise<TwitterWidgets> {
  if (widgetsPromise) return widgetsPromise;

  widgetsPromise = new Promise<TwitterWidgets>((resolve, reject) => {
    if (window.twttr?.widgets) {
      resolve(window.twttr);
      return;
    }

    const existing = document.querySelector<HTMLScriptElement>(`script[src="${WIDGETS_SRC}"]`);
    const script = existing ?? document.createElement("script");

    script.addEventListener("load", () => {
      if (window.twttr?.widgets) resolve(window.twttr);
      else reject(new Error("widgets.js loaded without installing window.twttr"));
    });
    script.addEventListener("error", () => reject(new Error("widgets.js blocked")));

    if (!existing) {
      script.src = WIDGETS_SRC;
      script.async = true;
      document.head.appendChild(script);
    }
  });

  return widgetsPromise;
}

/** Accepts a status URL and returns the numeric id createTweet needs. */
function parseStatusId(url: string): string | null {
  return url.match(/status\/(\d+)/)?.[1] ?? null;
}

function subscribeToTheme(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  return () => observer.disconnect();
}

function readTheme(): "dark" | "light" {
  return document.documentElement.getAttribute("data-theme") === "day" ? "light" : "dark";
}

/** Null on the server: there is no data-theme to read, and guessing would build
 *  the widget in the wrong colour before swapping it. */
function readThemeOnServer(): null {
  return null;
}

export default function XPostEmbed({ url }: { url: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, readThemeOnServer);
  const statusId = parseStatusId(url);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !statusId || theme === null) return;

    let cancelled = false;
    // The widget renders into an iframe we can't restyle, so a theme change means
    // tearing the whole thing down and asking X to build it again.
    host.replaceChildren();

    const timeout = window.setTimeout(() => {
      if (!cancelled) setFailed(true);
    }, RENDER_TIMEOUT_MS);

    loadWidgets()
      .then((twttr) =>
        twttr.widgets.createTweet(statusId, host, { theme, dwell: false, align: "center" }),
      )
      .then((rendered) => {
        if (cancelled) return;
        window.clearTimeout(timeout);
        // createTweet resolves with undefined when the post is deleted or private.
        setFailed(!rendered);
      })
      .catch(() => {
        if (cancelled) return;
        window.clearTimeout(timeout);
        setFailed(true);
      });

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [statusId, theme]);

  const showFallback = failed || !statusId;

  return (
    <div className="not-prose my-4">
      {/* Reserves height so the page doesn't jump when the widget resolves. */}
      <div ref={hostRef} className={showFallback ? "hidden" : "min-h-40"} />

      {showFallback && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between rounded-lg border border-line px-4 py-3 text-sm text-mist transition-colors hover:border-mist/60 hover:text-mist-bright"
        >
          <span>Watch the walkthrough on X</span>
          <span aria-hidden="true">&rarr;</span>
        </a>
      )}
    </div>
  );
}
