import type { SVGProps } from "react";

/**
 * Z.ai. Artwork from @lobehub/icons-static-svg (MIT); Z.ai is a
 * trademark of Z.ai.
 *
 * fillRule is required: several of these marks rely on even-odd winding for
 * their cut-outs and render as solid blobs without it.
 */
export default function ZaiIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" fillRule="evenodd" {...props}>
      <path d="M12.105 2L9.927 4.953H.653L2.83 2h9.276zM23.254 19.048L21.078 22h-9.242l2.174-2.952h9.244zM24 2L9.264 22H0L14.736 2H24z" />
    </svg>
  );
}
