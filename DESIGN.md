# Holocron — Design System

Dark archive ("ink and parchment at night"), not space-HUD. One theme; no light mode — the
constellation canvas is the identity and it needs the night sky.

## Color

OKLCH. All neutrals tinted toward the ink-blue brand hue (h≈255). Never #000/#fff.

| Token | OKLCH | Use |
|---|---|---|
| `--ink-950` | `oklch(0.16 0.02 255)` | app background |
| `--ink-900` | `oklch(0.19 0.02 255)` | panel background (chat) |
| `--ink-800` | `oklch(0.24 0.02 255)` | raised surfaces, input |
| `--ink-700` | `oklch(0.32 0.015 255)` | borders, dividers |
| `--parchment` | `oklch(0.92 0.012 85)` | primary text (warm) |
| `--parchment-dim` | `oklch(0.72 0.01 85)` | secondary text |
| `--parchment-faint` | `oklch(0.55 0.008 85)` | tertiary/labels |
| `--canon` | `oklch(0.72 0.13 235)` | canon continuity (sky) |
| `--legends` | `oklch(0.75 0.13 75)` | legends continuity (amber) |
| `--error` | `oklch(0.68 0.16 25)` | errors only |

Color strategy: **Restrained** on chrome (tinted neutrals), with the two continuity hues doing
all accent work — they are data encoding, not decoration (PRODUCT.md principle 2).

## Typography

- UI: Geist Sans (already loaded). Instrumentation (tool names, relations, sections): Geist Mono.
- Scale: 14 / 16 / 20 (≈1.25) for prose and headings; mono instrumentation runs
  smaller at 10–11px (breadcrumbs, relation tags, section labels) — instrument
  text is glanceable, not readable prose. Chat body 14; answers max-w-prose (~68ch).
- Headings by weight (600) + size, never color alone.

## Motion

- ease-out-quart (`cubic-bezier(0.25, 1, 0.5, 1)`), 150–300ms. Opacity/transform only.
- The graph supplies ambient motion (force settle, path particles); UI motion stays minimal.
- Streaming cursor: soft opacity pulse, not blink.

## Components

- **Citation chip**: pill, continuity-tinted bg at ~15% alpha + continuity text; the
  section lives in the title tooltip, not inline. Hover: 1px ring in the hue.
  This pattern is THE continuity affordance.
- **Tool breadcrumb**: mono 12px, parchment-faint, `→` separators.
- **Panels**: chat = ink-900; graph canvas = ink-950 (the darkest surface is the sky).
  NodePanel overlays ink-900 with a 1px ink-700 border, no glass blur.
- **Empty states**: one sentence of guidance + one example the user can click to run.

## Layout

Split-screen: chat 40% (min 24rem), graph 60% — the hero gets the space. Chat column:
header / scroll / composer, spacing 24px between turns, 6px inside a turn.
