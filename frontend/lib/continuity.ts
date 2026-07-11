// THE continuity theme (spec #26 decision 6): one owner for the hue pair that
// must stay identical across chat chips, graph nodes, and panel badges.
// layout.tsx injects `css` as the --canon/--legends vars; Tailwind classes and
// the canvas both read from here — change this file, everything follows.
import type { Continuity } from "./events";

export const CONTINUITY_THEME: Record<Continuity, { css: string; chip: string }> = {
  canon: {
    css: "oklch(0.72 0.13 235)",
    chip: "bg-canon/15 text-canon",
  },
  legends: {
    css: "oklch(0.75 0.13 75)",
    chip: "bg-legends/15 text-legends",
  },
};
