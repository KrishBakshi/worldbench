// Provider registry for test cards.
//
// This holds only the company label shown beneath the model name. The mark drawn
// behind it is the model's own logo and lives in components/icons, keyed by the
// same slug.

export interface Provider {
  /** Company name, shown along the bottom of the card. */
  name: string;
}

export const PROVIDERS: Record<string, Provider> = {
  anthropic: { name: "Anthropic" },
  openai: { name: "OpenAI" },
  google: { name: "Google" },
  xai: { name: "xAI" },
  alibaba: { name: "Alibaba" },
  moonshot: { name: "Moonshot AI" },
  zai: { name: "Z.ai" },
};

export function getProvider(slug: string | null): Provider | null {
  if (!slug) return null;
  return PROVIDERS[slug] ?? null;
}
