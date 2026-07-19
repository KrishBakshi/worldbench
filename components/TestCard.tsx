import Link from "next/link";
import type { Test } from "@/lib/tests";

export default function TestCard({
  test,
  compact = false,
}: {
  test: Test;
  compact?: boolean;
}) {
  return (
    <Link
      href={`/tests/${test.slug}`}
      className="group block overflow-hidden rounded-lg border border-line bg-void-deep/60 transition-colors hover:border-glow/60"
    >
      <div
        className={`relative w-full overflow-hidden bg-void-deep ${
          compact ? "aspect-[4/3]" : "aspect-video"
        }`}
      >
        {test.introMedia?.type === "video" ? (
          <video
            src={test.introMedia.src}
            autoPlay
            muted
            loop
            playsInline
            className="h-full w-full object-cover"
          />
        ) : test.introMedia?.type === "gif" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={test.introMedia.src} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs uppercase tracking-widest text-mist">
            {test.model}
          </div>
        )}
      </div>
      <div className={`flex items-center justify-between px-4 ${compact ? "py-2" : "py-3"}`}>
        <span className="text-sm text-mist-bright">{test.title}</span>
        {test.legacyPrompt && !compact && (
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] uppercase tracking-wide text-mist">
            legacy prompt
          </span>
        )}
      </div>
    </Link>
  );
}
