"use client";

import { useMemo, useState } from "react";
import type { Test } from "@/lib/tests";
import TestCard from "@/components/TestCard";

export interface ProviderOption {
  /** Provider slug, matching Test.provider. */
  slug: string;
  /** Company name shown on the badge. */
  name: string;
}

export default function TestBrowser({
  tests,
  providers,
}: {
  tests: Test[];
  providers: ProviderOption[];
}) {
  const [query, setQuery] = useState("");
  // One provider selected at a time; null means "all".
  const [active, setActive] = useState<string | null>(null);

  // Provider name by slug, so search can also match the company label.
  const providerName = useMemo(() => {
    const map = new Map<string, string>();
    for (const p of providers) map.set(p.slug, p.name);
    return map;
  }, [providers]);

  // Clicking the active badge again clears the filter.
  const select = (slug: string) =>
    setActive((prev) => (prev === slug ? null : slug));

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tests.filter((test) => {
      // A badge-based provider filter narrows to the selected provider.
      if (active && test.provider !== active) {
        return false;
      }
      if (!q) return true;
      const haystack = [
        test.title,
        test.model,
        test.summary,
        test.provider ? providerName.get(test.provider) ?? "" : "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [tests, query, active, providerName]);

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tests by name, model, or provider…"
          aria-label="Search tests"
          className="w-full border-0 border-b border-line bg-transparent px-0 py-2 text-sm text-mist-bright placeholder:text-mist focus:border-mist focus:outline-none"
        />

        <div className="flex flex-wrap gap-2">
          {providers.map((provider) => {
            const isActive = active === provider.slug;
            return (
              <button
                key={provider.slug}
                type="button"
                aria-pressed={isActive}
                onClick={() => select(provider.slug)}
                className={`rounded-md border px-3.5 py-1 text-xs uppercase tracking-[0.12em] transition-colors ${
                  isActive
                    ? "border-mist-bright bg-mist-bright text-void"
                    : "border-line text-mist hover:border-mist hover:text-mist-bright"
                }`}
              >
                {provider.name}
              </button>
            );
          })}
        </div>
      </div>

      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((test) => (
            <TestCard key={test.slug} test={test} />
          ))}
        </div>
      ) : (
        <p className="py-16 text-center text-sm text-mist">
          No tests match your search.
        </p>
      )}
    </div>
  );
}
