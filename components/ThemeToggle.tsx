"use client";

import { useEffect, useRef } from "react";
import { MoonIcon } from "@/components/animated-icons/moon-icon";
import { SunMediumIcon } from "@/components/animated-icons/sun-medium-icon";

/** Keep in sync with `--theme-swap` in globals.css. */
const THEME_SWAP_MS = 320;

export default function ThemeToggle() {
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function toggle() {
    const html = document.documentElement;
    const next = html.getAttribute("data-theme") === "day" ? "night" : "day";

    // Enable the global colour transition only for the swap itself, then drop
    // it so per-element hover transitions behave normally again.
    html.classList.add("theme-transition");
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      html.classList.remove("theme-transition");
    }, THEME_SWAP_MS);

    html.setAttribute("data-theme", next);
    window.localStorage.setItem("worldbench-theme", next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle theme"
      className="flex h-8 w-8 items-center justify-center text-mist-bright"
    >
      <MoonIcon size={18} className="hidden [html:not([data-theme='day'])_&]:block" />
      <SunMediumIcon size={18} className="hidden [html[data-theme='day']_&]:block" />
    </button>
  );
}
