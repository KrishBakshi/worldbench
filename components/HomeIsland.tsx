"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

/**
 * True once the island has revealed. Module-scoped so it survives client-side
 * navigation (going to /about and back) but resets on a full page load — so the
 * reveal plays when the site first loads and masks the image fetch, but not when
 * the user returns to the home page within the same session.
 *
 * Only written in an effect (never during render or on the server), so SSR
 * always emits the reveal class and the first client render matches it — no
 * hydration mismatch, no flash of the un-animated image.
 */
let hasRevealed = false;

export default function HomeIsland() {
  const [reveal] = useState(() => !hasRevealed);

  useEffect(() => {
    hasRevealed = true;
  }, []);

  return (
    <div className="absolute inset-0 z-10 translate-y-[14%] sm:translate-y-[11%]">
      <div className={`relative h-full w-full ${reveal ? "animate-island-reveal" : ""}`}>
        <Image
          src="/island.webp"
          alt="Floating biome island"
          fill
          sizes="(max-width: 768px) 90vw, 700px"
          className="animate-float object-contain select-none"
          priority
        />
      </div>
    </div>
  );
}
