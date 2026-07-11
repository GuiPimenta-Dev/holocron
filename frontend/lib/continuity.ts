// THE continuity theme (spec #26 decision 6): one owner for the hue pair that
// must stay identical across chat chips, graph nodes, and panel badges.
import type { Continuity } from "./events";

export const CONTINUITY_THEME: Record<Continuity, { hex: string; chip: string }> = {
  canon: {
    hex: "#0284c7", // sky-600
    chip: "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  },
  legends: {
    hex: "#d97706", // amber-600
    chip: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  },
};
