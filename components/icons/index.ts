import type { ComponentType, SVGProps } from "react";
import ClaudeIcon from "./claude";
import OpenAIIcon from "./openai";
import GeminiIcon from "./gemini";
import GrokIcon from "./grok";
import QwenIcon from "./qwen";
import KimiIcon from "./kimi";
import ZaiIcon from "./zai";
import AnthropicTextIcon from "./anthropic-text";
import OpenAITextIcon from "./openai-text";
import GoogleTextIcon from "./google-text";
import XaiTextIcon from "./xai-text";
import AlibabaTextIcon from "./alibaba-text";
import MoonshotTextIcon from "./moonshot-text";
import ZaiTextIcon from "./zai-text";
import type { WordmarkProps } from "./wordmark";

export type { WordmarkProps };

/**
 * Provider slug (from a test's `provider` frontmatter) to the mark drawn as the
 * card watermark. The mark is the *model's* logo, while the label under the
 * model name is the company — Claude for Anthropic, Gemini for Google, Qwen for
 * Alibaba, Kimi for Moonshot AI.
 *
 * Artwork is vendored from @lobehub/icons-static-svg (MIT) rather than taken as
 * a dependency: the React package `@lobehub/icons` peer-depends on antd and
 * @lobehub/ui, which would pull a whole UI framework into this site for seven
 * logos.
 */
export const PROVIDER_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  anthropic: ClaudeIcon,
  openai: OpenAIIcon,
  google: GeminiIcon,
  xai: GrokIcon,
  alibaba: QwenIcon,
  moonshot: KimiIcon,
  zai: ZaiIcon,
};

export function getProviderIcon(
  slug: string | null,
): ComponentType<SVGProps<SVGSVGElement>> | null {
  if (!slug) return null;
  return PROVIDER_ICONS[slug] ?? null;
}

/**
 * Provider slug to the *company* wordmark: Anthropic, OpenAI, Google. Set as
 * type rather than an icon, so it reads as an attribution line under the model
 * name instead of a second logo competing with the watermark.
 *
 * Same vendoring story as PROVIDER_ICONS — these are the `*-text` files from
 * @lobehub/icons-static-svg.
 */
export const PROVIDER_WORDMARKS: Record<string, ComponentType<WordmarkProps>> = {
  anthropic: AnthropicTextIcon,
  openai: OpenAITextIcon,
  google: GoogleTextIcon,
  xai: XaiTextIcon,
  alibaba: AlibabaTextIcon,
  moonshot: MoonshotTextIcon,
  zai: ZaiTextIcon,
};

/**
 * `size` is the rendered height of the whole 24-unit viewBox. Measuring the
 * artwork shows the set is already normalised: every mark has 2 units of side
 * padding and a 20-unit cap height on a shared baseline, so one `size` sets them
 * all at the same type size and the widths differ only because the names do —
 * "Anthropic" is longer than "xAI" for the same reason it is in running text.
 *
 * Cap height is therefore `size * 20 / 24`, but matching that to the cap height
 * of the neighbouring text overshoots badly: the marks are drawn bold, so at
 * equal cap height they carry far more weight than the regular-weight model name
 * above them and take over the card. They replace a 10px uppercase label, and
 * that is the size they want to be:
 *
 *   detail page  size 13 → 11px cap, under a 24px title
 *   card         size 11 →  9px cap, under a 16px model name
 *   card compact size  9 →  8px cap
 *
 * Upstream's docs demo these at `size={56}`, which is a showcase size: alone on
 * a white page, nothing to be subordinate to.
 */
export const WORDMARK_SIZE = { byline: 13, card: 11, cardCompact: 9 } as const;

/**
 * Per-mark correction on top of that base, set by eye against the rendered page.
 * A shared `size` gives every mark the same cap height, but not the same
 * presence: each logotype is drawn in its own face, and the lighter or smaller-
 * set ones read as shrunken next to Anthropic's heavy caps. Anthropic and
 * Moonshot sit at the base size; the rest are brought up to match.
 */
const WORDMARK_SCALE: Record<string, number> = {
  alibaba: 1.18,
  google: 1.25,
  xai: 1.25,
  openai: 1.2,
  zai: 1.1,
};

export function wordmarkSize(slug: string | null, base: number): number {
  return base * (slug ? (WORDMARK_SCALE[slug] ?? 1) : 1);
}

export function getProviderWordmark(
  slug: string | null,
): ComponentType<WordmarkProps> | null {
  if (!slug) return null;
  return PROVIDER_WORDMARKS[slug] ?? null;
}
