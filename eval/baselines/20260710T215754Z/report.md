# Eval report — run 20260710T215754Z

Baseline: 20260710T181909Z — cells show pass rate and delta.

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
| multi-hop | 87% (7/8) (+0pp) | 100% (8/8) (+13pp) | 87% (7/8) (+0pp) |
| continuity-conflict | 85% (6/7) (+57pp) | 100% (7/7) (+29pp) | 100% (7/7) (+15pp) |
| unanswerable | 100% (7/7) (+0pp) | 100% (7/7) (+0pp) | 100% (7/7) (+15pp) |

## ⚠ HALLUCINATIONS

- **agent/multi-hop-rey-father-species** (trace `fed75b9c49bb8c5415638098f1adb93a`): "What species was Rey's father?" — The expected chain is Rey -> father Dathan -> Human, but the answer fabricates an unstated 'Strand-Cast'/clone-of-Sidious link not among the expected facts and not covered by the cited titles, injecting an incorrect chain even though the final species (Human) is right.
- **vector-only/continuity-conflict-boba-fett-trainers** (trace `54953b4df0a97837e5bef882b098f260`): "Who trained Boba Fett?" — The answer names Jango Fett and Cad Bane as trainers in canon and Jango Fett in Legends, contradicting the expected behavior (Aurra Sing in both, plus Bossk in canon only) and failing to distinguish the continuities as specified.

## Flipped vs Baseline (judge)

- **regressed** agent/multi-hop-rey-father-species (trace `fed75b9c49bb8c5415638098f1adb93a`): "What species was Rey's father?"
- **regressed** vector-only/multi-hop-rey-father-species (trace `3f4b97db9e66781c422d928d24418e51`): "What species was Rey's father?"
- **fixed** agent/continuity-conflict-anakin-children (trace `fbb802e4fcc596d4cde26aaa47ddba1e`): "Who are Anakin Skywalker's children?"
- **fixed** agent/multi-hop-dooku-jedi-trainer-species (trace `d47ea8250704d5dda0a6619b7fc4e07f`): "What species is the Jedi who trained Dooku?"
- **fixed** agent/unanswerable-kessari-prime-location (trace `b5de92ebb75b030c05122145e4fcd759`): "In which sector is the planet Kessari Prime located?"
- **fixed** graph-only/continuity-conflict-anakin-children (trace `68635ce4a836227d1c865ea54060d219`): "Who are Anakin Skywalker's children?"
- **fixed** graph-only/continuity-conflict-boba-fett-trainers (trace `1cfc82fd794de3c05650c2d80083e3e9`): "Who trained Boba Fett?"
- **fixed** graph-only/multi-hop-rey-father-species (trace `329eb11642e44edb2354e252dad55242`): "What species was Rey's father?"
- **fixed** vector-only/continuity-conflict-2-1b-affiliations (trace `56de2bf81423c9458f02c371bbf5e1a9`): "Which organizations was the droid 2-1B affiliated with?"
- **fixed** vector-only/continuity-conflict-501st-headquarters (trace `581825828571347e9644fa3c562ea89e`): "Where was the 501st Legion headquartered?"
- **fixed** vector-only/continuity-conflict-anakin-children (trace `00e0f45276ead4fce7c16a316ca520ba`): "Who are Anakin Skywalker's children?"
- **fixed** vector-only/continuity-conflict-luke-trainers (trace `7b7d696ee871c7a29120e76f3cc7fcbf`): "Who trained Luke Skywalker?"
- **fixed** vector-only/multi-hop-dooku-jedi-trainer-species (trace `f40d19fa9b5a41807be5049036ff4897`): "What species is the Jedi who trained Dooku?"
