import GitHubIcon from "@/components/icons/github";

const REPO_URL = "https://github.com/KrishBakshi/worldbench";

/**
 * Header link to the project repository. Sits next to the theme toggle and
 * matches its 8x8 hit area; the mark is drawn in the muted chrome colour and
 * brightens on hover like the nav links.
 */
export default function GitHubLink() {
  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="View the worldbench repository on GitHub"
      className="flex h-8 w-8 items-center justify-center text-mist-bright transition-opacity hover:opacity-70"
    >
      <GitHubIcon width={18} height={18} aria-hidden="true" />
    </a>
  );
}
