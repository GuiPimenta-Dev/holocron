# Holocron

Star Wars lore agent that chooses at runtime between vector search and
knowledge-graph traversal, with a comparative eval as the project's centerpiece.

## Language

### Knowledge base

**Continuity**:
Which official Star Wars timeline a fact belongs to: `canon` or `legends`. Every
entity and chunk carries exactly one.
_Avoid_: universe, timeline, version

**Entity**:
An in-universe subject with its own wiki page (character, planet, weapon...).
Typed by its infobox; real-world pages (actors, films, companies) are not entities.
_Avoid_: article, page, node

**Topic**:
An entity without an infobox (concepts like Lightsaber or Blaster). Contributes
chunks but no relations.

**Chunk**:
A section-bounded slice of an entity's text; the unit of vector retrieval and
citation.
_Avoid_: passage, document

**Corpus**:
The pinned set of wiki pages the system knows. Anything outside it is
"unanswerable" by definition.

**Corpus Lock**:
The versioned manifest of (page title, revision id) that makes the corpus
reproducible. Two eval runs are comparable only under the same corpus lock.
_Avoid_: snapshot, dump

### Evaluation

**Golden Set**:
The versioned question suite, in four categories: single-hop, multi-hop,
continuity-conflict, and unanswerable.
_Avoid_: test set, benchmark

**Retrieval Strategy**:
One of the three compared configurations: vector-only, graph-only, or agent.
_Avoid_: mode, pipeline, variant

**Judge**:
The LLM that grades an answer against the rubric. Its model and rubric are
pinned independently of the system under test.

**Baseline**:
A saved eval run designated as the comparison reference. Scores are only ever
reported as deltas against a baseline.
