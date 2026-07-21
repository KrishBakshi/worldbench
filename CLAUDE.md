# worldbench: repo guide for Claude

This repo is the **worldbench** site: a Next.js (App Router) + TypeScript +
React, front-end-only portfolio for a single prompt. `prompts/prompt.md`
asks a model to generate a self-contained Three.js `world.html` of a floating
biome island directly (no JSON intermediate, no schema, no scoring). The
site lets people browse and interact with `world.html` outputs from
different models, compared visually.

**Models never see reference files.** Only `prompts/prompt.md` is
model-facing. `outputs/create.html` is a hand-tuned ideal world for humans,
used to judge results and to distill ecological / relational intent back
into that prompt. Never bake absolute dimensions, coordinates, or "copy
this file" language into the model-facing text.

## Layout
- `prompts/prompt.md`: the only model-facing prompt (copy-paste as-is).
- `prompts/README.md`: human notes for that prompt.
- `outputs/create.html`: ideal-world reference (human / qualitative only).
- `public/prompt.md`: a copy of `prompts/prompt.md`, served statically so
  the site can fetch/display it.
- `public/about/meta.mdx`: content for the About page (what worldbench is
  and the reasoning it tests), plus `public/about/island-info.png` (biome
  legend image, rendered on that page alongside a hand-built placement
  graph in `components/about/BiomeGraph.tsx`).
- `public/tests/<slug>/`: the site's content model. Each folder is one
  test: `meta.mdx` (frontmatter: `title`, `model`, `provider`, `date`,
  `pinned`, plus optional `summary`, `xPost`, and a notes body), an optional
  `intro.mp4` / `intro.webm` / `intro.gif`, and the actual `world.html`
  output. Adding a new test is just adding a new folder, no code changes
  needed. `pinned: true` tests (up to 4, most recent first) show on the home
  page under "See Recent Tests"; all tests show on `/tests`. `provider` keys
  into `lib/providers.ts` for the company name, and into
  `components/icons/index.ts` for two vendored marks: the model logo drawn as
  the card watermark, and the company wordmark (`*-text.tsx`) set as type
  under the model name on both the card and the detail page. Leave it out for
  non-model entries like the hand-tuned reference.
- `app/`: Next.js App Router pages: `/` (home, floating-island hero + recent
  tests), `/about` (what worldbench is), `/tests` (grid of all tests),
  `/tests/[slug]` (intro media + the live `world.html` embedded in an
  iframe).
- `components/`, `lib/tests.ts`, `lib/about.ts`: site code; the `lib/*.ts`
  files are the filesystem-based loaders for `public/tests/` and
  `public/about/`.
- `old/`: gitignored, local-only archive of the prior benchmark-era work
  (validators, schema, scored outputs, prior prompt pipeline). Not part of
  the live project; kept for reference only. It is also the source of the
  current seed tests in `public/tests/` (copied out, not itself shipped).

## Conventions
- Front-end only: no backend, no database, no API routes. `npm install &&
  npm run dev` to run it.
- Keep the home page minimal and sparse: no extra copy over the floating
  island animation beyond the header and "See Recent Tests".
- The header has exactly three links: Home, About, and View Tests. Don't
  add more without being asked.
- Keep `README.md` current. When a major commit is requested — a new page,
  a user-facing feature, or a change to the test frontmatter / folder
  layout — check whether the README still describes things accurately and
  update it in the same batch of work. Skip it for minor or internal-only
  changes.
