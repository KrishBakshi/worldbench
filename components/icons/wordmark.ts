import type { SVGProps } from "react";

/**
 * Props for the vendored `*-text` wordmarks, matching the API @lobehub/icons
 * gives its own `<Brand.Text size={n} />` components: `size` is the rendered
 * height, width follows from the viewBox.
 *
 * The components are vendored rather than imported from that package because
 * `import { XAI } from "@lobehub/icons"` resolves through a barrel that
 * re-exports its feature components, which pull in antd-style and peer-depend
 * on antd ^6 and @lobehub/ui ^5. The SVG paths here are the same artwork from
 * @lobehub/icons-static-svg, with none of that.
 */
export type WordmarkProps = Omit<SVGProps<SVGSVGElement>, "height"> & {
  /** Rendered height. Defaults to 1em, as the upstream components do. */
  size?: number | string;
};
