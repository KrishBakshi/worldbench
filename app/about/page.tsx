import { MDXRemote } from "next-mdx-remote/rsc";
import { getAbout, getPromptText } from "@/lib/about";
import BiomeGraph from "@/components/about/BiomeGraph";
import PromptDropdown from "@/components/about/PromptDropdown";
import IslandInfo from "@/components/about/IslandInfo";
import SocialLinks from "@/components/about/SocialLinks";

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

      <div className="prose mt-8 max-w-none text-sm">
        <MDXRemote
          source={about.content}
          components={{
            BiomeGraph,
            PromptDropdown: () => <PromptDropdown prompt={promptText} />,
            IslandInfo,
            SocialLinks,
          }}
        />
      </div>
    </section>
  );
}
