import Image from "next/image";
import RecentTests from "@/components/RecentTests";

export default function HomePage() {
  return (
    <div className="flex h-full flex-col">
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
  );
}
