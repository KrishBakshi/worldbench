import fs from "fs";
import path from "path";
import matter from "gray-matter";

const TESTS_DIR = path.join(process.cwd(), "public", "tests");

export interface IntroMedia {
  type: "video" | "gif";
  src: string;
}

export interface Test {
  slug: string;
  title: string;
  model: string;
  date: string;
  pinned: boolean;
  legacyPrompt: boolean;
  introMedia: IntroMedia | null;
  worldHtmlSrc: string;
  content: string;
}

function loadTest(slug: string): Test | null {
  const dir = path.join(TESTS_DIR, slug);
  const metaPath = path.join(dir, "meta.mdx");
  if (!fs.existsSync(metaPath)) return null;

  const raw = fs.readFileSync(metaPath, "utf8");
  const { data, content } = matter(raw);

  let introMedia: IntroMedia | null = null;
  for (const [file, type] of [
    ["intro.mp4", "video"],
    ["intro.webm", "video"],
    ["intro.gif", "gif"],
  ] as const) {
    if (fs.existsSync(path.join(dir, file))) {
      introMedia = { type, src: `/tests/${slug}/${file}` };
      break;
    }
  }

  return {
    slug,
    title: data.title ?? slug,
    model: data.model ?? "Unknown model",
    date: data.date ?? "",
    pinned: Boolean(data.pinned),
    legacyPrompt: Boolean(data.legacyPrompt),
    introMedia,
    worldHtmlSrc: `/tests/${slug}/world.html`,
    content: content.trim(),
  };
}

export function getAllTests(): Test[] {
  if (!fs.existsSync(TESTS_DIR)) return [];
  return fs
    .readdirSync(TESTS_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => loadTest(entry.name))
    .filter((test): test is Test => test !== null)
    .sort((a, b) => b.date.localeCompare(a.date));
}

export function getPinnedTests(limit = 4): Test[] {
  return getAllTests()
    .filter((test) => test.pinned)
    .slice(0, limit);
}

export function getTestBySlug(slug: string): Test | undefined {
  return getAllTests().find((test) => test.slug === slug);
}
