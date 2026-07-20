import { createElement } from "react";
import type { Test } from "@/lib/tests";
import { getProvider } from "@/lib/providers";
import {
  WORDMARK_SIZE,
  getProviderIcon,
  getProviderWordmark,
  wordmarkSize,
} from "@/components/icons";
import LiquidCard from "@/components/LiquidCard";

export default function TestCard({
  test,
  compact = false,
}: {
  test: Test;
  compact?: boolean;
}) {
  const provider = getProvider(test.provider);
  // Kept lowercase and rendered via createElement: a capitalized binding here
  // trips react-hooks/static-components, which reads it as building a component
  // during render rather than looking one up from a static map.
  const icon = getProviderIcon(test.provider);
  // The company wordmark, set as type under the model name.
  const wordmark = getProviderWordmark(test.provider);

  return (
    <LiquidCard href={`/tests/${test.slug}`}>
      <div
        className={`relative flex w-full flex-col items-center justify-center overflow-hidden px-4 ${
          compact ? "aspect-[4/3]" : "aspect-video"
        }`}
      >
        {/* Watermark. Sits behind the text and is cropped by the card, so it
            reads as a graphic field rather than a centred logo. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex items-center justify-center"
        >
          {icon ? (
            createElement(icon, {
              // Rest must contrast the card (light on dark / dark on light).
              // Hover flips against the liquid fill (black on white / white on
              // black) so the mark stays visible in both states. Scale and
              // opacity motion are unchanged.
              className:
                "h-[56%] w-[56%] scale-[0.99] text-white opacity-[0.07] transition-[opacity,transform,color] duration-500 ease-out group-hover:scale-[1.01] group-hover:text-black group-hover:opacity-[0.28] [[data-theme=day]_&]:text-black [[data-theme=day]_&]:group-hover:text-white",
            })
          ) : provider ? (
            // A known provider with no vendored mark yet: its initial stands in.
            <span className="font-display scale-[0.99] text-[5.5rem] leading-none font-bold text-white opacity-[0.06] transition-[opacity,transform,color] duration-500 ease-out select-none group-hover:scale-[1.01] group-hover:text-black group-hover:opacity-[0.26] [[data-theme=day]_&]:text-black [[data-theme=day]_&]:group-hover:text-white">
              {provider.name.charAt(0)}
            </span>
          ) : null}
          {/* Entries with no provider (the hand-tuned reference) get no mark —
              falling back to the title's initial just renders a stray glyph. */}
        </div>

        <span
          className={`relative text-center font-display leading-tight text-mist-bright transition-colors duration-300 group-hover:text-void ${
            compact ? "text-sm" : "text-base"
          }`}
        >
          {test.title}
        </span>

        <span className="relative mt-2 flex items-center text-[10px] uppercase tracking-[0.18em] text-mist transition-colors duration-300 group-hover:text-void/70">
          {provider && wordmark ? (
            createElement(wordmark, {
              size: wordmarkSize(
                test.provider,
                compact ? WORDMARK_SIZE.cardCompact : WORDMARK_SIZE.card,
              ),
              role: "img",
              "aria-label": provider.name,
            })
          ) : (
            <>{provider?.name ?? "Hand-tuned"}</>
          )}
        </span>
      </div>
    </LiquidCard>
  );
}
