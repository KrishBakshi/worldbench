"use client";

import Link from "next/link";
import { LiquidButton } from "@/components/animate-ui/primitives/buttons/liquid";
import { cn } from "@/lib/utils";

/**
 * The home-page call to action. Reuses the same liquid-fill primitive as the
 * test cards — a rising fill of mist-bright (white in dark mode, near-black in
 * day) — so the text inverts to void as the fill covers it.
 */
export default function ExploreEvaluationsButton() {
  return (
    <LiquidButton
      asChild
      // Match LiquidCard exactly so the fill animates at the same speed and feel
      // as the test cards. `delay` is the primitive's transition duration; left
      // unset it falls back to 0.3s, which read slower than the cards' 0.2s.
      delay="0.2s"
      fillHeight="4px"
      hoverScale={1.02}
      tapScale={0.98}
      className={cn(
        "relative inline-flex items-center justify-center overflow-hidden rounded-md",
        "border border-line px-7 py-3",
        "font-display text-xs uppercase tracking-[0.2em]",
        // hover:, not group-hover: — the button is the hovered element itself, so
        // the text inverts to void as the fill (mist-bright) rises to cover it.
        "text-mist-bright transition-[color,border-color] duration-300 hover:text-void hover:border-mist/60",
        // Rest fill background and the fill colour, mirroring LiquidCard.
        "[--liquid-button-background-color:color-mix(in_srgb,var(--color-void-deep)_60%,transparent)]",
        "[--liquid-button-color:#ffffff] [[data-theme=day]_&]:[--liquid-button-color:#121214]",
      )}
    >
      <Link href="/tests">Explore Evaluations</Link>
    </LiquidButton>
  );
}
