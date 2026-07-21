"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { useHeroReveal } from "@/lib/heroReveal";

/**
 * Fades its children up into place on the first load only. On a client-side
 * return to the page it renders them statically — same first-load-only gating
 * as the hero text and island (see useHeroReveal). Used for the call-to-action
 * button, which sits below the heading and tagline.
 */
export default function RevealFade({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const reveal = useHeroReveal();

  if (!reveal) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
