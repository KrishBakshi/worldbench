"use client";

import { useEffect, useRef } from "react";

type GravityStarsBackgroundProps = {
  className?: string;
  /** Star count at the reference viewport; scaled by actual area. */
  starsCount?: number;
  /** Base star radius at the reference width; scaled by actual width. */
  starsSize?: number;
  /** Opacity of a star lit fully by the pointer. At rest stars sit far dimmer. */
  starsOpacity?: number;
  glowIntensity?: number;
  /** How a star's glow catches up to its proximity target. */
  glowAnimation?: "instant" | "ease" | "spring";
  /** Ambient drift speed in px/frame. */
  movementSpeed?: number;
  /** Radius in px within which the pointer affects a star. */
  mouseInfluence?: number;
  mouseGravity?: "attract" | "repel";
  gravityStrength?: number;
};

type Star = {
  x: number;
  y: number;
  /** Ambient drift. Constant — never damped, so the field never settles. */
  dx: number;
  dy: number;
  /** Pointer-induced impulse. Damped back to zero as the pointer moves away. */
  vx: number;
  vy: number;
  r: number;
  twinkle: number;
  twinkleSpeed: number;
  /** 0 = resting/dim, 1 = fully lit by the pointer. Eased toward its target. */
  glow: number;
  /** Spring velocity for `glowAnimation: "spring"`. */
  glowV: number;
};

/** The theme tokens are plain hex, so a small parser beats pulling in a dep. */
function parseHex(value: string): [number, number, number] | null {
  let hex = value.trim().replace(/^#/, "");
  if (hex.length === 3) {
    hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
  }
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return null;
  const n = Number.parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

const REFERENCE_AREA = 1600 * 900;
const REFERENCE_WIDTH = 1600;
/** Per-frame decay of the pointer impulse. */
const DAMPING = 0.94;
/** Share of `starsOpacity` a star keeps when the pointer is nowhere near it. */
const REST_OPACITY = 0.28;
/** Per-frame approach rate for `glowAnimation: "ease"`. */
const GLOW_EASE = 0.09;
const GLOW_SPRING_STIFFNESS = 0.14;
const GLOW_SPRING_DAMPING = 0.72;
/** Keep in sync with `--theme-swap` in globals.css. */
const THEME_SWAP_MS = 320;

export default function GravityStarsBackground({
  className,
  starsCount = 160,
  starsSize = 2.4,
  starsOpacity = 0.75,
  glowIntensity = 15,
  glowAnimation = "ease",
  movementSpeed = 0.12,
  mouseInfluence = 200,
  mouseGravity = "attract",
  gravityStrength = 75,
}: GravityStarsBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let stars: Star[] = [];
    let frame = 0;
    let color = "rgb(240, 240, 242)";
    // Canvas paint can't inherit the CSS theme transition, so the star colour is
    // faded by hand — linearly, over the same duration, so it lands with it.
    let rgb: [number, number, number] = [240, 240, 242];
    let fadeFrom: [number, number, number] = [240, 240, 242];
    let fadeTo: [number, number, number] = [240, 240, 242];
    /** Timestamp the running fade began, or 0 once settled. */
    let fadeStart = 0;

    const pointer = { x: 0, y: 0, active: false };

    function seedStars() {
      const areaScale = Math.min(Math.max((width * height) / REFERENCE_AREA, 0.5), 3.5);
      const sizeScale = Math.min(Math.max(width / REFERENCE_WIDTH, 0.7), 1.8);
      const count = Math.round(starsCount * areaScale);
      const size = starsSize * sizeScale;

      stars = Array.from({ length: count }, () => {
        const angle = Math.random() * Math.PI * 2;
        const speed = movementSpeed * (0.4 + Math.random() * 0.9);
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          dx: Math.cos(angle) * speed,
          dy: Math.sin(angle) * speed,
          vx: 0,
          vy: 0,
          r: size * (0.6 + Math.random() * 0.8),
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: 0.01 + Math.random() * 0.02,
          glow: 0,
          glowV: 0,
        };
      });
    }

    // Size the backing store from the canvas's own laid-out box (set by the
    // positioning classes the caller passes in), never from the parent — the
    // canvas is viewport-fixed and spans more than its parent's content box.
    function measure() {
      if (!canvas || !ctx) return;
      const rect = canvas.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function readColor({ immediate = false } = {}) {
      const value = getComputedStyle(document.documentElement)
        .getPropertyValue("--color-mist-bright")
        .trim();
      const parsed = parseHex(value);
      if (!parsed) return;

      if (immediate) {
        rgb = [...parsed];
        fadeFrom = [...parsed];
        fadeTo = [...parsed];
        fadeStart = 0;
        return;
      }
      if (parsed.every((c, i) => c === fadeTo[i])) return;

      fadeFrom = [...rgb];
      fadeTo = parsed;
      fadeStart = performance.now();
    }

    function resize() {
      measure();
      seedStars();
    }

    // The canvas sits behind page content, so it never receives pointer events
    // itself. Track the pointer on the window and convert into canvas space.
    function handlePointerMove(e: PointerEvent) {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      pointer.x = e.clientX - rect.left;
      pointer.y = e.clientY - rect.top;
      pointer.active = true;
    }

    function handlePointerLeave() {
      pointer.active = false;
    }

    function step() {
      if (!ctx) return;
      ctx.clearRect(0, 0, width, height);

      // `color` is assigned unconditionally: on a fresh mount there is no fade
      // running, and deriving it only mid-fade would leave every star painted
      // in the initial default (invisible in whichever theme it doesn't match).
      if (fadeStart) {
        const t = Math.min((performance.now() - fadeStart) / THEME_SWAP_MS, 1);
        rgb = fadeFrom.map((c, i) => c + (fadeTo[i] - c) * t) as typeof rgb;
        if (t >= 1) fadeStart = 0;
      }
      color = `rgb(${Math.round(rgb[0])}, ${Math.round(rgb[1])}, ${Math.round(rgb[2])})`;

      const dir = mouseGravity === "attract" ? 1 : -1;

      for (const star of stars) {
        // Proximity in 0..1, shared by the gravity pull and the glow target so
        // a star brightens exactly as far as the pointer reaches it.
        let proximity = 0;

        if (pointer.active) {
          const dx = pointer.x - star.x;
          const dy = pointer.y - star.y;
          const dist = Math.hypot(dx, dy);
          if (dist < mouseInfluence && dist > 0.01) {
            proximity = 1 - dist / mouseInfluence;
            // Linear falloff to zero at the influence radius. With DAMPING this
            // settles at ~(force / (1 - DAMPING)) px/frame of pull.
            const force = (gravityStrength / 1000) * proximity;
            star.vx += (dx / dist) * force * dir;
            star.vy += (dy / dist) * force * dir;
          }
        }

        if (glowAnimation === "instant") {
          star.glow = proximity;
        } else if (glowAnimation === "spring") {
          star.glowV += (proximity - star.glow) * GLOW_SPRING_STIFFNESS;
          star.glowV *= GLOW_SPRING_DAMPING;
          star.glow += star.glowV;
        } else {
          star.glow += (proximity - star.glow) * GLOW_EASE;
        }
        // A spring can overshoot past either end; keep it usable as an alpha.
        const lit = Math.min(Math.max(star.glow, 0), 1);

        star.vx *= DAMPING;
        star.vy *= DAMPING;

        star.x += star.dx + star.vx;
        star.y += star.dy + star.vy;

        // Wrap so the field stays uniformly populated.
        if (star.x < -star.r) star.x += width + star.r * 2;
        else if (star.x > width + star.r) star.x -= width + star.r * 2;
        if (star.y < -star.r) star.y += height + star.r * 2;
        else if (star.y > height + star.r) star.y -= height + star.r * 2;

        star.twinkle += star.twinkleSpeed;
        const twinkleFactor = 0.6 + 0.4 * Math.sin(star.twinkle);

        ctx.save();
        // Dim at rest, ramping to full `starsOpacity` under the pointer.
        ctx.globalAlpha =
          starsOpacity * (REST_OPACITY + (1 - REST_OPACITY) * lit) * twinkleFactor;
        ctx.shadowColor = color;
        // Halo only where the pointer reaches, so the field stays flat elsewhere.
        ctx.shadowBlur = glowIntensity * lit;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      frame = requestAnimationFrame(step);
    }

    readColor({ immediate: true });
    resize();

    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    document.addEventListener("pointerleave", handlePointerLeave);

    // The palette is swapped by flipping data-theme on <html>.
    const themeObserver = new MutationObserver(() => readColor());
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    frame = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(frame);
      themeObserver.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("pointerleave", handlePointerLeave);
    };
  }, [
    starsCount,
    starsSize,
    starsOpacity,
    glowIntensity,
    glowAnimation,
    movementSpeed,
    mouseInfluence,
    mouseGravity,
    gravityStrength,
  ]);

  // `h-full w-full` is not optional: <canvas> is a replaced element, so inset-0
  // alone leaves it at its intrinsic 300x150 instead of filling the box.
  return (
    <canvas
      ref={canvasRef}
      className={`h-full w-full ${className ?? ""}`}
      aria-hidden="true"
    />
  );
}
