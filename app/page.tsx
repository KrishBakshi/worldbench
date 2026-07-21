import Image from "next/image";
import GravityStarsBackground from "@/components/backgrounds/GravityStarsBackground";
import ExploreEvaluationsButton from "@/components/ExploreEvaluationsButton";

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
            <h1 className="absolute inset-x-0 top-[-8%] z-0 flex flex-col items-center gap-1.5 text-center font-display text-2xl leading-[0.95] font-bold tracking-[-0.015em] sm:top-[-6%] sm:gap-2 sm:text-4xl md:text-5xl">
              <span className="text-mist-bright">Intelligence Has Landscapes</span>
              <span className="text-transparent [-webkit-text-stroke:1.25px_var(--color-mist-bright)] sm:[-webkit-text-stroke:1.5px_var(--color-mist-bright)]">
                Explore Them
              </span>
            </h1>

            <div className="absolute inset-0 z-10 translate-y-[14%] sm:translate-y-[11%]">
              <Image
                src="/island.webp"
                alt="Floating biome island"
                fill
                sizes="(max-width: 768px) 90vw, 700px"
                className="animate-float object-contain select-none"
                priority
              />
            </div>
          </div>

          {/* Bottom half kept as is: tagline caption, then the call to action. */}
          <p className="animate-tagline mt-10 text-center font-display text-xs uppercase tracking-[0.35em] text-mist sm:text-sm">
            Pushing intelligent reasoning{" "}
            <span className="text-mist-bright">into the unknown</span>
          </p>
          <div className="mt-6">
            <ExploreEvaluationsButton />
          </div>
        </section>
      </div>
    </>
  );
}
