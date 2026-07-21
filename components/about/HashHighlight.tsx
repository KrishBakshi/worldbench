"use client";

import { useEffect } from "react";

/**
 * Applies the highlight to whichever heading the URL fragment points at — e.g.
 * arriving at /about#what-is-worldbench from the header's info button.
 *
 * This is done in JS rather than with CSS `:target` because Next's client-side
 * navigation sets the hash without activating `:target`, so the pure-CSS version
 * never fired on a link click. Runs on mount (covers navigating in) and on
 * hashchange (covers clicking another anchor while already here), re-triggering
 * the flash each time.
 */
export default function HashHighlight() {
  useEffect(() => {
    function apply() {
      const id = decodeURIComponent(window.location.hash.slice(1));
      if (!id) return;
      const el = document.getElementById(id);
      if (!el) return;

      el.classList.remove("is-highlighted");
      // Force a reflow so re-adding the class restarts the flash animation.
      void el.offsetWidth;
      el.classList.add("is-highlighted");
    }

    apply();
    window.addEventListener("hashchange", apply);
    return () => window.removeEventListener("hashchange", apply);
  }, []);

  return null;
}
