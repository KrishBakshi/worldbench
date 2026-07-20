import SocialLinks from "@/components/about/SocialLinks";

/**
 * Rendered by the test detail page for every test, rather than authored into each
 * meta.mdx — otherwise the same block has to be pasted into every test folder and
 * kept in sync. Mirrors the closing section of public/about/meta.mdx.
 */
export default function ContributeCTA() {
  return (
    <section className="mt-12 border-t border-line pt-6">
      <h2 className="font-display text-base text-mist-bright">Got a different result?</h2>
      <p className="mt-2 text-sm text-mist">
        No two runs land on the same island. If yours turns out genuinely great, or
        wonderfully broken, post it and tag me. I&apos;d love to see how yours came out.
      </p>
      <SocialLinks />
    </section>
  );
}
