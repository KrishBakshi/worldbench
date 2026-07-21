"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/** How far down the scroller must be before the button appears. */
const THRESHOLD = 300;

/**
 * A back-to-top button pinned to the bottom-right. worldbench scrolls inside
 * <main> (the app-shell), not the document, so this listens to and scrolls that
 * element rather than window. Appears past a threshold and, like the reference,
 * dims while scrolling down and brightens on the way up.
 *
 * md+ only: on mobile the bottom edge is taken by the "best on desktop" notice,
 * and short pages swipe up easily.
 */
export default function ScrollToTopButton() {
  const [visible, setVisible] = useState(false);
  const [direction, setDirection] = useState<"up" | "down">("down");

  useEffect(() => {
    const scroller = document.querySelector("main");
    if (!scroller) return;

    let prev = scroller.scrollTop;
    function onScroll() {
      const top = scroller!.scrollTop;
      setVisible(top >= THRESHOLD);
      if (Math.abs(top - prev) > 2) {
        setDirection(top > prev ? "down" : "up");
        prev = top;
      }
    }

    onScroll();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    return () => scroller.removeEventListener("scroll", onScroll);
  }, []);

  function toTop() {
    const el = document.querySelector("main");
    if (!el) return;

    // Native smooth scroll doesn't animate on this nested scroller, so ease it
    // by hand. Directly setting scrollTop works where scrollTo({behavior}) won't.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.scrollTop = 0;
      return;
    }

    const start = el.scrollTop;
    const startTime = performance.now();
    const duration = 450;
    function step(now: number) {
      const t = Math.min(1, (now - startTime) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      el!.scrollTop = start * (1 - eased);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  return (
    <button
      type="button"
      onClick={toTop}
      aria-label="Scroll to top"
      className={cn(
        "fixed right-6 bottom-6 z-40 hidden h-10 w-10 items-center justify-center rounded-md",
        "border border-line bg-void-deep/80 text-mist backdrop-blur md:flex",
        "transition-[opacity,color,transform] duration-300 hover:text-mist-bright",
        visible
          ? direction === "down"
            ? "opacity-40 hover:opacity-100"
            : "opacity-100"
          : "pointer-events-none translate-y-2 opacity-0",
      )}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="h-5 w-5"
        aria-hidden="true"
      >
        <line x1="12" y1="19" x2="12" y2="5" />
        <polyline points="5 12 12 5 19 12" />
      </svg>
    </button>
  );
}
