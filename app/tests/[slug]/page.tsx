import Link from "next/link";
import { notFound } from "next/navigation";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getAllTests, getTestBySlug } from "@/lib/tests";
import WorldEmbed from "@/components/tests/WorldEmbed";

export function generateStaticParams() {
  return getAllTests().map((test) => ({ slug: test.slug }));
}

export default async function TestDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const test = getTestBySlug(slug);
  if (!test) notFound();

  return (
    <section className="mx-auto max-w-3xl px-6 py-10 md:px-10">
      <Link href="/tests" className="text-sm text-mist hover:text-mist-bright">
        &larr; Back
      </Link>

      <div className="mt-6 flex items-center justify-between">
        <h1 className="font-display text-2xl text-mist-bright">{test.title}</h1>
        {test.legacyPrompt && (
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] uppercase tracking-wide text-mist">
            legacy prompt
          </span>
        )}
      </div>
      <p className="mt-1 text-sm text-mist">{test.model}</p>

      {test.introMedia && (
        <div className="mt-8 aspect-video w-full overflow-hidden rounded-lg border border-line">
          {test.introMedia.type === "video" ? (
            <video
              src={test.introMedia.src}
              autoPlay
              muted
              loop
              playsInline
              className="h-full w-full object-cover"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={test.introMedia.src} alt="" className="h-full w-full object-cover" />
          )}
        </div>
      )}

      <div className="mt-8">
        <WorldEmbed src={test.worldHtmlSrc} />
      </div>

      {test.content && (
        <div className="prose mt-8 max-w-none text-sm">
          <MDXRemote source={test.content} />
        </div>
      )}
    </section>
  );
}
