/**
 * A plain link out to the post. Embedding it — either via widgets.js or
 * react-tweet — brought the whole thread in with it: these posts quote an
 * earlier test, and both carry video, so the card read as two posts stacked
 * under the world it was meant to annotate.
 */
export default function XPostEmbed({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-2 text-sm text-mist transition-colors hover:text-mist-bright"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5 fill-current">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
      <span className="underline underline-offset-2">Check this test on X</span>
      {/* Up-and-right arrow: the usual sign that the link leaves for a new tab. */}
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="h-3.5 w-3.5"
      >
        <path d="M7 17 17 7" />
        <path d="M8 7h9v9" />
      </svg>
    </a>
  );
}
