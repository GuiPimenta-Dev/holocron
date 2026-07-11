# Eval report — run 20260711T110335Z

Baseline: 20260711T110335Z — cells show pass rate and delta.

## Citation check

| Category | vector-only | graph-only | agent |
|---|---|---|---|
| single-hop | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) |
| multi-hop | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) |
| continuity-conflict | 85% (6/7) (+0pp) | 100% (7/7) (+0pp) | 100% (7/7) (+0pp) |

## Judge

| Category | vector-only | graph-only | agent |
|---|---|---|---|
| single-hop | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) | 100% (8/8) (+0pp) |
| multi-hop | 100% (8/8) (+0pp) | 87% (7/8) (+0pp) | 87% (7/8) (+0pp) |
| continuity-conflict | 57% (4/7) (+0pp) | 100% (7/7) (+0pp) | 100% (7/7) (+0pp) |
| unanswerable | 100% (7/7) (+0pp) | 100% (7/7) (+0pp) | 100% (7/7) (+0pp) |

## ⚠ HALLUCINATIONS

- **agent/multi-hop-dooku-jedi-trainer-species** (trace `7074c28a3205d289aef8b746420dffdc`): "What species is the Jedi who trained Dooku?" — The chain to Yoda as Dooku's Jedi master is correct, but the answer treats the placeholder "Yoda's species" as an actual recorded species name rather than stating Yoda's (unnamed) species, so the required species fact is fabricated rather than delivered.
- **graph-only/multi-hop-dooku-jedi-trainer-species** (trace `4c5583ea605da072c83a0406627bbb52`): "What species is the Jedi who trained Dooku?" — The answer contradicts itself and ultimately claims Yoda's species is not recorded in the corpus, contradicting the expected fact that it is listed as 'Yoda's species', so the species half of the chain is not correctly stated.
- **vector-only/continuity-conflict-anakin-children** (trace `c4004b5caa0af50f8710666cb23f0411`): "Who are Anakin Skywalker's children?" — The answer blends continuities by asserting both canon and Legends record Luke and Leia, but the corpus's Legends page records only Luke — a contradiction of the expected continuity behavior.
- **vector-only/continuity-conflict-barriss-offee-trainers** (trace `e9d667ff2cc2da218b172ac9879854bd`): "Who trained Barriss Offee?" — The answer explicitly states Luminara Unduli trained Offee in both canon and Legends but omits Anakin Skywalker for canon, and instead of distinguishing continuities it introduces Stass Allie as the canon second trainer — contradicting the expected behavior that canon lists Anakin Skywalker.
- **vector-only/continuity-conflict-boba-fett-trainers** (trace `830ed333814fe8eaa85a31119ae5e673`): "Who trained Boba Fett?" — The answer gets the continuity distinction wrong — it frames canon-only training around Cad Bane and omits Aurra Sing (expected in both) and Bossk (expected canon-only), contradicting the expected continuity behavior.
- **vector-only/continuity-conflict-501st-headquarters** (trace `a70f4e523b823d0bc3c53b3529d6a885`): "Where was the 501st Legion headquartered?" — The answer contradicts the expected behavior by claiming the canon corpus specifies no headquarters, when canon should list Coruscant.
