const links = [
  { label: "X", href: "https://x.com/KrishBakshi_" },
  { label: "LinkedIn", href: "https://linkedin.com/in/krish-bakshi-8b85b6314/" },
  { label: "GitHub", href: "https://github.com/KrishBakshi" },
];

export default function SocialLinks() {
  return (
    <ul className="not-prose my-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {links.map((link) => (
        <li key={link.href}>
          <a
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-mist underline underline-offset-2 transition-colors hover:text-mist-bright"
          >
            {link.label}
          </a>
        </li>
      ))}
    </ul>
  );
}
