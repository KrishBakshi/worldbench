import Link from "next/link";

/**
 * The small "what is this?" affordance beside the wordmark: an info button that
 * links to the top of /about, where the intro paragraph explains what worldbench
 * is. The label rides along in a tooltip styled after shadcn/radix — a dark
 * rounded popover with an arrow that fades in — but built in CSS rather than
 * pulling in Radix, matching how the rest of the repo vendors small UI.
 *
 * `group` drives it: the tooltip reveals on hover and on keyboard focus
 * (focus-within), and `aria-label` carries the same text for screen readers, so
 * the visual tooltip itself is decorative.
 */
export default function AboutTooltipLink() {
  return (
    <span className="group relative inline-flex">
      <Link
        href="/about#what-is-worldbench"
        aria-label="What is worldbench?"
        className="flex size-5 items-center justify-center rounded-full text-mist transition-colors hover:text-mist-bright focus-visible:text-mist-bright focus-visible:outline-none"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="size-3.5"
        >
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4" />
          <path d="M12 8h.01" />
        </svg>
      </Link>

      {/* Tooltip. pointer-events-none so it never intercepts the click; the delay
          on reveal mirrors radix's default open delay. */}
      <span
        role="tooltip"
        className="pointer-events-none absolute top-full left-1/2 mt-2 -translate-x-1/2 scale-95 rounded-md bg-mist-bright px-2.5 py-1 text-xs whitespace-nowrap text-void opacity-0 shadow-md transition-[opacity,transform] duration-150 group-hover:scale-100 group-hover:opacity-100 group-hover:delay-300 group-focus-within:scale-100 group-focus-within:opacity-100"
      >
        What is worldbench?
        {/* Arrow: a rotated square tucked under the popover's top edge. */}
        <span
          aria-hidden="true"
          className="absolute -top-1 left-1/2 size-2 -translate-x-1/2 rotate-45 rounded-[1px] bg-mist-bright"
        />
      </span>
    </span>
  );
}
