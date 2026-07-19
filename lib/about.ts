import fs from "fs";
import path from "path";
import matter from "gray-matter";

const ABOUT_PATH = path.join(process.cwd(), "public", "about", "meta.mdx");
const PROMPT_PATH = path.join(process.cwd(), "public", "prompt.md");

export interface About {
  title: string;
  description: string;
  content: string;
}

export function getAbout(): About | null {
  if (!fs.existsSync(ABOUT_PATH)) return null;

  const raw = fs.readFileSync(ABOUT_PATH, "utf8");
  const { data, content } = matter(raw);

  return {
    title: data.title ?? "About",
    description: data.description ?? "",
    content: content.trim(),
  };
}

export function getPromptText(): string {
  if (!fs.existsSync(PROMPT_PATH)) return "";
  return fs.readFileSync(PROMPT_PATH, "utf8").trim();
}
