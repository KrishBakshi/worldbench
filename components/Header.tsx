"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";
import AboutTooltipLink from "@/components/AboutTooltipLink";

const links = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/tests", label: "View Tests" },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="relative z-10 grid h-16 shrink-0 grid-cols-3 items-center px-6 md:px-10">
      <div className="flex items-center gap-2 justify-self-start">
        <Link
          href="/"
          className="font-display text-sm uppercase tracking-[0.2em] text-mist-bright"
        >
          worldbench
        </Link>
        <AboutTooltipLink />
      </div>
      <nav className="flex justify-self-center gap-8 text-xs uppercase tracking-[0.15em]">
        {links.map((link) => {
          const active =
            link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={
                active
                  ? "text-mist-bright"
                  : "text-mist transition-colors hover:text-mist-bright"
              }
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
      <div className="justify-self-end">
        <ThemeToggle />
      </div>
    </header>
  );
}
