# Eval report — run 20260710T181909Z

Baseline: none — **absolute numbers**, comparable only to future runs.

## Citation check

| Category | vector-only | graph-only | agent |
|---|---|---|---|
| single-hop | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| multi-hop | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| continuity-conflict | 85% (6/7) | 100% (7/7) | 100% (7/7) |

## Judge

| Category | vector-only | graph-only | agent |
|---|---|---|---|
| single-hop | 100% (8/8) | 100% (8/8) | 100% (8/8) |
| multi-hop | 87% (7/8) | 87% (7/8) | 87% (7/8) |
| continuity-conflict | 28% (2/7) | 71% (5/7) | 85% (6/7) |
| unanswerable | 100% (7/7) | 100% (7/7) | 85% (6/7) |

## ⚠ HALLUCINATIONS

- **agent/multi-hop-dooku-jedi-trainer-species**: "What species is the Jedi who trained Dooku?" — The answer never states Yoda's species (the second expected fact) and instead insists the species has 'deliberately never been revealed' and 'no species designation is given,' contradicting the expected fact that Yoda is of Yoda's (unnamed but distinct) species — and it injects an unrequested Sith-master claim, so the multi-hop chain to the species fact is missing/contradicted.
- **agent/continuity-conflict-anakin-children**: "Who are Anakin Skywalker's children?" — The answer correctly states canon has Luke and Leia and Legends lists only Luke, but then blends in outside lore claiming Leia is 'also traditionally his daughter' in Legends, contradicting the corpus's Legends record of Luke only.
- **agent/unanswerable-kessari-prime-location**: "In which sector is the planet Kessari Prime located?" — Though hedged, the answer asserts substantive lore facts (Kessel is in the Kessel sector of the Outer Rim, appearing in canon and Legends) in response to a fabricated subject, which the rubric marks as a hallucinated failure.
- **graph-only/continuity-conflict-anakin-children**: "Who are Anakin Skywalker's children?" — The answer correctly reports canon (Luke, Leia) and the Legends corpus (Luke only), but then overrides the corpus with external lore by asserting Leia is also his Legends daughter and dismissing the corpus as incomplete, contradicting the expected continuity behavior that the Legends page records only Luke.
- **graph-only/continuity-conflict-boba-fett-trainers**: "Who trained Boba Fett?" — The answer blends continuities by attributing Bossk to canon-only correctly but adds an unsupported 'donor'/Jango Fett trainer claim and, critically, omits Bossk'wassak'Cradossk from the Legends listing while the expected behavior says Legends lists Aurra Sing (which it does) — however it fabricates a canon/Legends split framing that contradicts by treating Jango as a listed trainer, contradicting the expected two-fact attribution.
- **vector-only/continuity-conflict-anakin-children**: "Who are Anakin Skywalker's children?" — The answer blends the continuities by claiming Leia is Anakin's child in both canon and Legends, contradicting the expected behavior that the corpus's Legends page records only Luke.
- **vector-only/continuity-conflict-boba-fett-trainers**: "Who trained Boba Fett?" — The answer names Jango Fett as Boba's trainer in both continuities and never mentions Aurra Sing or Bossk'wassak'Cradossk, contradicting the expected continuity behavior (canon: Aurra Sing + Bossk'wassak'Cradossk; Legends: Aurra Sing).
- **vector-only/continuity-conflict-luke-trainers**: "Who trained Luke Skywalker?" — The answer blends the continuities by claiming Luke's training was 'consistent in both canon and Legends' with only Kenobi and Yoda, omitting that Legends also lists Palpatine and thus contradicting the expected distinction between the two continuities.
- **vector-only/continuity-conflict-2-1b-affiliations**: "Which organizations was the droid 2-1B affiliated with?" — The answer fails the expected per-continuity breakdown: it claims the individual 2-1B was affiliated only with the Rebel Alliance in both continuities and relegates the Galactic Empire and New Republic to a separate model-line discussion, contradicting the expected behavior that canon lists Empire + Alliance and Legends adds the New Republic.
