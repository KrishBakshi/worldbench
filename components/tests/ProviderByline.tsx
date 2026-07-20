import { createElement } from "react";
import { getProvider } from "@/lib/providers";
import { WORDMARK_SIZE, getProviderWordmark, wordmarkSize } from "@/components/icons";

/**
 * The line under a test's title. The title is already the model name, so
 * repeating it there said nothing; the company behind the model is the piece of
 * information that was missing.
 *
 * Drawn as the vendored wordmark where one exists, since set type reads better
 * at this size than the company name in the body face.
 */
export default function ProviderByline({ provider: slug }: { provider: string | null }) {
  const provider = getProvider(slug);
  // Lowercase and rendered via createElement to match components/TestCard.tsx:
  // a capitalized binding trips react-hooks/static-components.
  const wordmark = getProviderWordmark(slug);

  // Entries with no provider (the hand-tuned reference) get no byline.
  if (!provider) return null;

  return (
    <p className="mt-2 flex items-center text-mist">
      {wordmark ? (
        createElement(wordmark, {
          size: wordmarkSize(slug, WORDMARK_SIZE.byline),
          role: "img",
          "aria-label": provider.name,
        })
      ) : (
        <span className="text-sm">{provider.name}</span>
      )}
    </p>
  );
}
