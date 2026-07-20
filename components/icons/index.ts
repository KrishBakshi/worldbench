import type { ComponentType, SVGProps } from "react";
import ClaudeIcon from "./claude";
import OpenAIIcon from "./openai";
import GeminiIcon from "./gemini";
import GrokIcon from "./grok";
import QwenIcon from "./qwen";
import KimiIcon from "./kimi";
import ZaiIcon from "./zai";

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
