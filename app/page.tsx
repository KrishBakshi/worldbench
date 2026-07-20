import Image from "next/image";
import GravityStarsBackground from "@/components/backgrounds/GravityStarsBackground";
import RecentTests from "@/components/RecentTests";

export default function HomePage() {
  return (
    <>
      {/* Fixed to the viewport so the starfield sits behind the header and the
          recent-tests row, not just the hero. */}
      <GravityStarsBackground className="fixed inset-0 z-0" mouseGravity="repel" />
      <div className="relative z-10 flex h-full flex-col">
        <section className="flex min-h-0 flex-1 items-center justify-center px-6">
          <div className="relative h-full max-h-[52vh] w-full max-w-3xl">
            <Image
              src="/island.png"
              alt="Floating biome island"
              fill
              sizes="(max-width: 768px) 90vw, 700px"
              className="animate-float object-contain select-none"
              priority
            />
          </div>
        </section>
        <RecentTests />
      </div>
    </>
  );
}
