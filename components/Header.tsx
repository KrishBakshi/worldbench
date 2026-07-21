"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";
import AboutTooltipLink from "@/components/AboutTooltipLink";
import MobileNav from "@/components/MobileNav";

const links = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/tests", label: "View Tests" },
];

export default function Header() {
  const pathname = usePathname();

  return (
    <header className="relative z-40 flex h-16 shrink-0 items-center justify-between px-6 md:grid md:grid-cols-3 md:px-10">
      <div className="flex items-center gap-2 justify-self-start">
        <Link
          href="/"
          className="font-display text-sm uppercase tracking-[0.2em] text-mist-bright"
        >
          worldbench
        </Link>
        <AboutTooltipLink />
      </div>
      <nav className="hidden justify-self-center gap-8 text-xs uppercase tracking-[0.15em] md:flex">
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
      <div className="flex items-center gap-1 justify-self-end">
        <ThemeToggle />
        <MobileNav links={links} />
      </div>
    </header>
  );
}
