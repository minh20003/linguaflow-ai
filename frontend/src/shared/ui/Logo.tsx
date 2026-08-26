"use client";

import { useId } from "react";

interface LogoProps {
  /** Rendered size in pixels. The mark is drawn on a 32-unit grid and scales cleanly. */
  size?: number;
  /** Set on the wrapping svg when the mark stands alone; omit when a text label is beside it. */
  title?: string;
  className?: string;
}

/**
 * The LinguaFlow mark.
 *
 * A speech bubble carrying two lines: the upper one knocked out of the bubble,
 * the lower one shorter and in the action accent. It reads as a message and its
 * translation rather than as a generic chat icon, which is the one thing that
 * distinguishes this product from every other messenger.
 *
 * The bubble is painted in `currentColor` so the same mark sits on the deep
 * purple navigation rail and on a cream page without a second asset, and the
 * knocked-out line lets whatever is behind it show through. Only the accent bar
 * is a fixed colour.
 */
export default function Logo({ size = 28, title, className }: LogoProps) {
  // Two logos on one page would otherwise share a mask id and the second would
  // silently render unmasked.
  const maskId = `linguaflow-mark-${useId()}`;

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role={title ? "img" : "presentation"}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {title && <title>{title}</title>}
      <mask id={maskId}>
        <rect width="32" height="32" fill="#ffffff" />
        <rect x="9" y="10" width="14" height="2.6" rx="1.3" fill="#000000" />
      </mask>
      <path
        d="M9 4h15a6 6 0 0 1 6 6v8a6 6 0 0 1-6 6h-9l-6 5v-5a6 6 0 0 1-6-6v-8a6 6 0 0 1 6-6z"
        fill="currentColor"
        mask={`url(#${maskId})`}
      />
      <rect x="9" y="15.4" width="9" height="2.6" rx="1.3" fill="var(--accent-action, #FEA837)" />
    </svg>
  );
}
