"use client";

import { useEffect, useState } from "react";

/**
 * True until the hero has revealed once. Module-scoped so it survives
 * client-side navigation (going to /about and back) but resets on a full page
 * load — so the hero entrance plays only on the first load of the site, and
 * never again when the user returns to the home page within the same session.
 *
 * Mirrors the flag in components/HomeIsland.tsx so the text, the button, and the
 * island all reveal together on first load and all stay put on return.
 */
let hasRevealed = false;

/**
 * Returns whether the hero entrance should animate. True only on the first
 * load; false on any client-side return to the page.
 *
 * The flag is written in an effect (never during render or on the server), so
 * SSR and the first client render both see `true` — no hydration mismatch.
 */
export function useHeroReveal(): boolean {
  const [reveal] = useState(() => !hasRevealed);

  useEffect(() => {
    hasRevealed = true;
  }, []);

  return reveal;
}
