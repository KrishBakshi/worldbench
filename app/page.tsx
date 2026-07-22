import GravityStarsBackground from "@/components/backgrounds/GravityStarsBackground";
import HomeIsland from "@/components/HomeIsland";
import ExploreEvaluationsButton from "@/components/ExploreEvaluationsButton";
import RevealText from "@/components/RevealText";
import RevealFade from "@/components/RevealFade";

export default function HomePage() {
  return (
    <>
      {/* Fixed to the viewport so the starfield sits behind the header and the
          recent-tests row, not just the hero. */}
      <GravityStarsBackground className="fixed inset-0 z-0" mouseGravity="repel" />
      <div className="relative z-10 flex h-full flex-col">
        <section className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 pb-28 sm:pb-0">
          {/* Layered hero: the heading sits behind the floating island, up near
              the top so the mountain rises into it. Line one is solid; line two
              is a hollow outline that hovers over the peaks. */}
          <div className="relative aspect-[3/2] w-full max-w-3xl sm:aspect-auto sm:h-[52vh]">
            {/* The heading animates in character-by-character (MagicUI
                TextAnimate), but only on the first load — RevealText renders it
                statically on a client-side return (see useHeroReveal). Each line
                is its own run so the outline styling on line two is kept and it
                lands a beat after line one. */}
            <h1 className="absolute inset-x-0 top-[-8%] z-0 flex flex-col items-center gap-1.5 text-center font-display text-2xl leading-[0.95] font-bold tracking-[-0.015em] sm:top-[-6%] sm:gap-2 sm:text-4xl md:text-5xl">
              <RevealText
                as="span"
                by="character"
                animation="blurInUp"
                startOnView={false}
                delay={0.15}
                className="text-mist-bright"
              >
                Intelligence Has Landscapes
              </RevealText>
              <RevealText
                as="span"
                by="character"
                animation="blurInUp"
                startOnView={false}
                delay={0.4}
                className="text-transparent [-webkit-text-stroke:1.25px_var(--color-mist-bright)] sm:[-webkit-text-stroke:1.5px_var(--color-mist-bright)]"
              >
                Explore Them
              </RevealText>
            </h1>

            <HomeIsland />
          </div>

          {/* Tagline caption, then the call to action. The caption blurs in
              (MagicUI TextAnimate) a beat after the heading settles — first load
              only, via RevealText. */}
          <RevealText
            as="h1"
            animation="blurIn"
            startOnView={false}
            delay={1.05}
            className="mt-10 text-center font-display text-xs uppercase tracking-[0.35em] text-mist sm:text-sm"
          >
            Pushing intelligent reasoning into the unknown
          </RevealText>
          {/* The liquid-fill CTA fades up last, also first load only. */}
          <RevealFade className="mt-6" delay={1.35}>
            <ExploreEvaluationsButton />
          </RevealFade>
        </section>
      </div>
    </>
  );
}
