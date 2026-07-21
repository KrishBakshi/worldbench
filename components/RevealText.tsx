"use client";

import { createElement, type ComponentProps } from "react";
import { TextAnimate } from "@/components/magicui/text-animate";
import { useHeroReveal } from "@/lib/heroReveal";

type Props = ComponentProps<typeof TextAnimate>;

/**
 * Wraps TextAnimate so the entrance plays only on the first load. On a
 * client-side return to the page it renders the final text statically (same
 * element and classes), skipping the animation — see useHeroReveal.
 */
export default function RevealText({ children, className, as = "p", ...rest }: Props) {
  const reveal = useHeroReveal();

  if (reveal) {
    return (
      <TextAnimate as={as} className={className} {...rest}>
        {children}
      </TextAnimate>
    );
  }

  return createElement(as, { className }, children);
}
