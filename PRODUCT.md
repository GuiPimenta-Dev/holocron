# Holocron — Product Context

Derived from spec #26 (grilled 2026-07-10), ADR-0003, and CONTEXT.md. Adjust via `/impeccable teach`.

## Register

product — an app UI where design serves the demonstration. But craft quality is itself a stated
goal: the frontend exists as a job-market signal (ADR-0003), so "serviceable" is failure.

## Users

1. **Recruiters / hiring managers** — click the demo from the README, decide in 90 seconds
   whether the candidate is worth an interview. They won't read code; the UI carries the claim.
2. **Engineers reviewing the repo** — want to see honest engineering: real tool calls, real
   data, no fake magic. They distrust anything that looks like a template.
3. **The developer** — demos it live; the 3-minute arc (ask → watch the graph grow) is the pitch.

## Product Purpose

Make the agent's invisible runtime decision VISIBLE. The product's one claim: this agent chooses
between knowledge-graph traversal and vector search per question, and you can watch it happen.
The live graph is not decoration; it IS the evidence.

## Brand Personality

The Holocron of the lore: an ancient archive artifact that lights up when a seeker questions it.
Quiet, precise, archival. An observatory reading room, not a spaceship cockpit. Confidence
through restraint; wonder through the data itself (constellations forming), never through
decoration.

## Anti-references

- Generic AI chat wrappers: centered bubble chat, avatar circles, "typing..." theater.
- SaaS dashboard clichés: hero metrics, icon-card grids, gradient CTAs.
- Star Wars kitsch: starfield wallpapers, Aurebesh display fonts, yellow title crawls,
  lightsaber cursors. The lore is the content, never the costume.
- "AI-generated look": purple gradients, glassmorphism, identical rounded cards.

## Strategic Design Principles

1. **The graph is the hero.** The canvas gets the space, the contrast, and the motion budget.
   Chat is the instrument panel: compact, legible, subordinate.
2. **Continuity is the color system.** Canon and Legends hues are the ONLY accent colors
   anywhere; everything else is tinted neutral. If a third accent appears, it's drift.
3. **Honest instrumentation.** Tool names, relation types, and sections appear as they are
   (SCREAMING_SNAKE and all) — monospace, like the instrument it is.
4. **The empty state teaches.** First load must communicate "ask, and watch the graph think"
   without a tutorial.

## Theme scene

The seeker opens the archive at night: a dim reading room, one warm lamp, a deep-ink sky in the
window where constellations of knowledge light up as questions are asked. Dark, but archival
dark (ink and parchment), not space-HUD dark (black and neon).
