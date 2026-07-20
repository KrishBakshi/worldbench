import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getAllTests, getTestBySlug } from "@/lib/tests";
import WorldEmbed from "@/components/tests/WorldEmbed";
import XPostEmbed from "@/components/tests/XPostEmbed";
import ContributeCTA from "@/components/tests/ContributeCTA";
import SocialLinks from "@/components/about/SocialLinks";
import BiomeGraph from "@/components/about/BiomeGraph";

export function generateStaticParams() {
  return getAllTests().map((test) => ({ slug: test.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const test = getTestBySlug(slug);
  if (!test) return {};

  const description = test.summary || `${test.model} generating a floating biome island.`;

  return {
    title: `${test.title} — worldbench`,
    description,
    openGraph: {
      title: `${test.title} — worldbench`,
      description,
    },
  };
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

      <h1 className="mt-6 font-display text-2xl text-mist-bright">{test.title}</h1>
      <p className="mt-1 text-sm text-mist">{test.model}</p>

      {test.summary && <p className="mt-4 text-sm text-mist">{test.summary}</p>}

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

      {test.xPostUrl && (
        <div className="mt-4">
          <XPostEmbed url={test.xPostUrl} />
        </div>
      )}

      {test.content && (
        <div className="prose mt-8 max-w-none text-sm">
          <MDXRemote source={test.content} components={{ SocialLinks, BiomeGraph }} />
        </div>
      )}

      <ContributeCTA />
    </section>
  );
}
