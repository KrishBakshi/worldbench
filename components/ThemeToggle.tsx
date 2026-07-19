"use client";

import { MoonIcon } from "@/components/animated-icons/moon-icon";
import { SunMediumIcon } from "@/components/animated-icons/sun-medium-icon";

export default function ThemeToggle() {
  function toggle() {
    const html = document.documentElement;
    const next = html.getAttribute("data-theme") === "day" ? "night" : "day";
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
