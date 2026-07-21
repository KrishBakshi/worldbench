"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/**
 * A Notion-style table of contents: a slim rail of right-aligned bars pinned to
 * the side of the viewport that expands into a labelled panel on hover, with the
 * bar/entry for the section currently in view highlighted.
 *
 * It's content-agnostic on purpose so it can sit alongside any long-form page:
 * rather than re-parsing a markdown source, it reads the already-rendered
 * headings out of the DOM (assigning slugified `id`s to any that lack one so the
 * entries are still scroll-linkable). Point it at a container with
 * `contentSelector` and drop it next to that container.
 *
 * Hidden below `xl` — it lives in the right margin, which only exists on wide
 * viewports; narrow layouts get nothing rather than an overlap.
 */

interface Heading {
  id: string;
  text: string;
  level: number;
}

export interface TableOfContentsProps {
  /** CSS selector for the element whose headings to index. */
  contentSelector: string;
  /** Label shown above the list in the expanded panel. */
  title?: string;
  /** Heading levels to include, e.g. `[2, 3]` for `<h2>`/`<h3>`. Defaults to 2–3. */
  levels?: number[];
  className?: string;
}

/** "What is worldbench" -> "what-is-worldbench". Only used for headings that
 *  don't already carry an id, so existing anchor schemes are left untouched. */
function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\w]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Levels are collapsed to two visual tiers: the lowest included level reads as
 *  a top-level "section", everything deeper is nested. */
function isSection(heading: Heading, topLevel: number) {
  return heading.level <= topLevel;
}

export function TableOfContents({
  contentSelector,
  title,
  levels = [2, 3],
  className,
}: TableOfContentsProps) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState<string>("");

  const topLevel = Math.min(...levels);

  // Read headings from the rendered DOM. Re-runs if the target selector or the
  // set of levels changes.
  useEffect(() => {
    const container = document.querySelector(contentSelector);
    if (!container) return;

    const selector = levels.map((l) => `h${l}`).join(",");
    const found: Heading[] = [];

    container.querySelectorAll<HTMLElement>(selector).forEach((el) => {
      const text = el.textContent?.trim() ?? "";
      if (!text) return;
      if (!el.id) el.id = slugify(text);
      const level = Number(el.tagName.slice(1));
      found.push({ id: el.id, text, level });
    });

    setHeadings(found);
  }, [contentSelector, levels]);

  // Track which heading is currently in view to drive the active highlight.
  useEffect(() => {
    if (headings.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActiveId(entry.target.id);
        });
      },
      { rootMargin: "-100px 0px -66% 0px" }
    );

    const elements = headings
      .map((h) => document.getElementById(h.id))
      .filter((el): el is HTMLElement => el !== null);

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [headings]);

  const scrollToHeading = (id: string) => {
    const element = document.getElementById(id);
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth" });
    setActiveId(id);
  };

  if (headings.length === 0) return null;

  return (
    <nav
      aria-label={title ? `${title} — table of contents` : "Table of contents"}
      className={cn(
        "group fixed top-1/2 right-8 z-40 hidden -translate-y-1/2 xl:block",
        className
      )}
    >
      {/* Expanded panel: revealed on hover of the rail. */}
      <div className="pointer-events-none absolute top-1/2 right-0 flex w-56 -translate-y-1/2 translate-x-4 flex-col gap-1.5 rounded-md border border-line bg-void-deep p-3.5 opacity-0 shadow-xl transition-all duration-300 group-hover:pointer-events-auto group-hover:translate-x-0 group-hover:opacity-100">
        {title && (
          <h4 className="mb-1.5 line-clamp-2 px-1.5 font-mono text-[13px] font-semibold leading-snug text-mist">
            {title}
          </h4>
        )}
        <ul className="flex flex-col gap-0.5">
          {headings.map((heading) => {
            const section = isSection(heading, topLevel);
            const active = activeId === heading.id;
            return (
              <li key={heading.id} className={cn(!section && "pl-2.5")}>
                <button
                  type="button"
                  onClick={() => scrollToHeading(heading.id)}
                  className={cn(
                    "w-full rounded px-1.5 text-left font-mono leading-snug transition-colors hover:bg-line/50",
                    section
                      ? "py-1 text-[13px] font-semibold"
                      : "py-0.5 text-xs",
                    active
                      ? "bg-line/50 font-medium text-mist-bright"
                      : section
                        ? "text-mist-bright/80"
                        : "text-mist"
                  )}
                >
                  {heading.text}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Collapsed rail: right-aligned bars, hidden while the panel is open. */}
      <ul className="flex w-full flex-col gap-3 py-4 opacity-100 transition-opacity duration-300 group-hover:opacity-0">
        {headings.map((heading) => {
          const section = isSection(heading, topLevel);
          const active = activeId === heading.id;
          return (
            <li key={heading.id} className="flex w-full justify-end">
              <button
                type="button"
                onClick={() => scrollToHeading(heading.id)}
                aria-label={`Scroll to ${heading.text}`}
                className={cn(
                  "ml-auto block h-[2px] shrink-0 rounded-full transition-all duration-300",
                  section
                    ? active
                      ? "w-7 bg-mist-bright"
                      : "w-5 bg-mist/30 hover:w-6 hover:bg-mist-bright"
                    : active
                      ? "w-6 bg-mist-bright"
                      : "w-4 bg-mist/30 hover:w-5 hover:bg-mist-bright"
                )}
              />
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default TableOfContents;
