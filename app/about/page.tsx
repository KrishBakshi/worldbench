import type { ComponentProps, ReactNode } from "react";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getAbout, getPromptText } from "@/lib/about";
import BiomeGraph from "@/components/about/BiomeGraph";
import PromptDropdown from "@/components/about/PromptDropdown";
import IslandInfo from "@/components/about/IslandInfo";
import SocialLinks from "@/components/about/SocialLinks";
import HashHighlight from "@/components/about/HashHighlight";
import TableOfContents from "@/components/ui/TableOfContents";

/** "What is worldbench" -> "what-is-worldbench", so headings are linkable. */
function slugify(node: ReactNode): string | undefined {
  if (typeof node !== "string") return undefined;
  return node
    .toLowerCase()
    .replace(/[^\w]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Gives every section heading an id anchor. `scroll-mt` keeps the target clear
 *  of the header when linked to directly, e.g. the info button's #what-is-worldbench. */
function H2({ children, ...props }: ComponentProps<"h2">) {
  return (
    <h2 id={slugify(children)} className="w-fit scroll-mt-24 rounded -mx-2 px-2" {...props}>
      {children}
    </h2>
  );
}

export default function AboutPage() {
  const about = getAbout();
  const promptText = getPromptText();
  if (!about) return null;

  return (
    <section className="mx-auto max-w-3xl px-6 py-10 md:px-10">
      <h1 className="font-display text-2xl text-mist-bright">{about.title}</h1>
      {about.description && (
        <p className="mt-1 text-sm text-mist">{about.description}</p>
      )}

      <HashHighlight />

      <div id="about-content" className="prose mt-8 max-w-none text-sm">
        <MDXRemote
          source={about.content}
          components={{
            h2: H2,
            BiomeGraph,
            PromptDropdown: () => <PromptDropdown prompt={promptText} />,
            IslandInfo,
            SocialLinks,
          }}
        />
      </div>

      <TableOfContents
        contentSelector="#about-content"
        title={about.title}
        levels={[2]}
      />
    </section>
  );
}
