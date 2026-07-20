"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import {
  LiquidButton,
  type LiquidButtonProps,
} from "@/components/animate-ui/primitives/buttons/liquid";
import { cn } from "@/lib/utils";

type LiquidCardProps = Omit<LiquidButtonProps, "asChild" | "children"> & {
  href: string;
  children: ReactNode;
  className?: string;
};

export default function LiquidCard({
  href,
  children,
  className,
  delay = "0.2s",
  fillHeight = "4px",
  hoverScale = 1.02,
  tapScale = 0.98,
  ...props
}: LiquidCardProps) {
  return (
    <LiquidButton
      asChild
      delay={delay}
      fillHeight={fillHeight}
      hoverScale={hoverScale}
      tapScale={tapScale}
      className={cn(
        "group relative block overflow-hidden rounded-lg border border-line",
        // Rest: deep void. Hover fill: solid mist-bright — white in dark mode,
        // near-black in day — so the liquid reads as a full invert, not gray.
        "[--liquid-button-background-color:color-mix(in_srgb,var(--color-void-deep)_60%,transparent)]",
        "[--liquid-button-color:#ffffff] [[data-theme=day]_&]:[--liquid-button-color:#121214]",
        "transition-[border-color] hover:border-mist/60",
        className,
      )}
      {...props}
    >
      <Link href={href}>{children}</Link>
    </LiquidButton>
  );
}
