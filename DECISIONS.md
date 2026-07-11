# Holocron — Decisions Doc

> Agente de lore de Star Wars com GraphRAG e eval comparativo.
> Decisões fechadas em sessão de grilling, 2026-07-09.

**Pitch de CV:** Agente que decide em runtime entre busca vetorial e travessia de grafo de conhecimento para responder perguntas de lore, com eval comparativo mostrando onde cada estratégia falha — incluindo desambiguação de continuidades contraditórias (Canon vs Legends).

## Decisões

| # | Galho | Decisão | Racional |
|---|---|---|---|
| 1 | Alvo do CV | Vaga de AI/LLM Engineer | Mercado atual paga agentes/RAG/evals; o projeto inteiro otimiza pra isso |
| 2 | Domínio | Star Wars (Wookieepedia) | Divertido, reconhecível, e a divisão Canon vs Legends dá conflito de fontes real — o melhor ângulo de eval |
| 3 | Corpus | ~5-15k artigos: Canon + Legends das eras dos filmes (personagens, planetas, eventos, organizações) | Pequeno o bastante pra reindexar num fim de semana, grande o bastante pra multi-hop ser difícil. Wookieepedia inteira (200k) é cauda irrelevante |
| 4 | Ingestão | API MediaWiki do Fandom por categorias → wikitext bruto cacheado em disco → parse offline com `mwparserfromhell` | Wikitext preserva infoboxes intactas; reprodutível via script. Licença CC-BY-SA ok com atribuição |
| 5 | Construção do grafo | Determinística: infoboxes viram arestas tipadas (`treinou`, `membro_de`, `nasceu_em`...), links entre artigos viram arestas `relacionado`. Zero LLM | Grafo limpo em horas, custo ~zero, sem alucinação. Extração via LLM é cara, ruidosa e extrai pior que a infobox que já existe. Híbrido (LLM no texto corrido) é fase 2 SE o eval mostrar gap |
| 6 | Arquitetura | Agente com 2 ferramentas — busca vetorial e consulta ao grafo — escolhendo por pergunta em runtime | É genuinamente agêntico (decisão em runtime), e a comparação A/B/C do eval É o portfólio. Multi-agente seria overengineering |
| 7 | Tool de grafo | Funções tipadas (`get_entity`, `get_relations`, `path_between`) + escape hatch `run_cypher` read-only | Tipadas = robustas, eval limpo; Cypher livre pra perguntas exóticas + keyword "text-to-Cypher" no CV |
| 8 | Stack | Python + ~~Pydantic AI~~ **LangGraph** ([ADR-0001](docs/adr/0001-langgraph-over-pydantic-ai.md)) + Neo4j (local, Docker) + ~~LanceDB~~ pgvector (#39) + Claude Sonnet no agente | Neo4j/Cypher: keyword real de CV. LanceDB: vetor embutido, zero infra. LangGraph substituiu Pydantic AI por alinhamento com o mercado |
| 9 | Eval | Golden set ~~≈100~~ **30 perguntas v0 (spec #11; schema pronto para crescer a 100)** em 4 categorias: (1) factual 1-hop, (2) multi-hop relacional, (3) conflito Canon vs Legends, (4) sem-resposta-no-corpus. LLM-judge (~~Sonnet~~ **Opus via `claude -p`**, ver spec #11: julgar o sistema com o próprio modelo convida self-preference bias) com rubrica + checagem determinística de citação. Roda contra vetor-só, grafo-só e agente | As categorias expõem onde cada retrieval falha; a categoria 4 mede alucinação. A tabela resultante é a peça central do README. RAGAS genérico não conta a história Canon/Legends |
| 10 | Demo | Local apenas — sem deploy. Web UI mínima (Streamlit): pergunta, resposta com citações marcadas por continuidade, painel com as tool calls do agente. GIF disso no README | Sem deploy = sem custo/abuso, Sonnet fica viável. O README carrega 100% do peso: GIF + tabela de eval são obrigatórios |
| 11 | Escopo/tempo | ~3-4 fins de semana, fases incrementais, cada uma termina demonstrável | Projetos de portfólio morrem 80% construídos; cada fase já vale algo |

## Decididos por padrão (gritar se discordar)

- **Embeddings:** `voyage-3-lite` ou `text-embedding-3-small` — barato, tanto faz qual.
- **Continuidade como metadado desde o dia 1:** campo `continuity: canon|legends` em todo chunk e todo nó do grafo. Sustenta a categoria de eval mais interessante; retrofitar depois dói.

## Fases

1. **FDS 1:** scrape + parse de infobox + índice vetorial (LanceDB) + grafo (Neo4j)
2. **FDS 2:** agente + tools + UI local mínima
3. **FDS 3:** golden set + harness de eval + tabela comparativa A/B/C
4. **FDS 4:** GIF, README, escrita final

**v0-que-já-vale** (corte mínimo pro CV): ingestão + vetor + grafo + agente 2-tools + eval de 30 perguntas + README com tabela.

## Meta-setup (sessão 2, 2026-07-09)

| # | Galho | Decisão | Racional |
|---|---|---|---|
| 12 | Repo | Este diretório (`~/Gui/grill`) é o repo do Holocron; git init feito | CLAUDE.md e skills versionados junto do código |
| 13 | Governança | CLAUDE.md enxuto + 2 skills cirúrgicas (`run-eval`, `add-tool`) | Skill só pra ritual multi-passo recorrente; `ingest` é um comando, `write-golden-questions` é trabalho de uma fase só |
| 14 | Toolchain | uv + ruff + pyright + pytest | Stack 2026; tools tipadas são a fronteira do agente — pyright pega erro ali |
| 15 | Testes | pytest obrigatório p/ parsers e tools (fixtures reais); agente só via eval; zero mock de LLM | Mock de LLM é teatro; eval é o teste de integração do agente |
| 16 | CI | GitHub Actions: lint + pytest apenas. Eval roda manual por fase | Eval em CI = custo de API a cada push |
| 17 | Doc de arquitetura | Seção no próprio CLAUDE.md (diagrama + regras de fronteira); sem ARCHITECTURE.md | Um lugar só; DECISIONS.md guarda os porquês |
| 18 | Idioma/schema | Tudo em inglês (código, README, golden set). Arestas SCREAMING_SNAKE (TRAINED_BY, MEMBER_OF), labels por tipo (Character, Planet) | Recrutador internacional; padrão Neo4j. Schema completo NÃO se define agora — emerge do parse na fase 1 |

## Emendas da fase 1 (2026-07-09, aprendidas da API real)

| # | Emenda | O que a realidade mostrou |
|---|---|---|
| 19 | Corpus por **crawl de links dos 11 filmes** (depth 1, ranqueado por nº de filmes que linkam), não por categorias | A taxonomia da Wookieepedia é fragmentada em milhares de micro-categorias ("7th Sky Corps personnel") — inutilizável pra recorte. Depth-1 dos filmes dá ~24k links; o ranking por frequência entre filmes torna o `--cap` uma amostra de centralidade, não alfabética |
| 20 | Tipo da entidade vem do **nome do template da infobox** (`{{Character}}`, `{{Celestialbody}}`) | Melhor que categoria: determinístico e 1:1 com a página |
| 21 | Filtro de mundo real via flags do `{{Top}}`: `real`/`rw*` descartam a página (atores, filmes, produtoras, páginas de ano) | Os links mais frequentes dos filmes são os créditos (George Lucas, ILM) — sem esse filtro o grafo vira IMDb |
| 22 | Página in-universe **sem infobox** vira tipo `Topic`: sem arestas, mas com chunks | Conceitos centrais (Lightsaber, Blaster, Sith) não têm infobox — descartá-los mataria o índice vetorial |
| 23 | Fetcher resolve **redirects** e persiste o mapa (`data/redirects.json`); arestas resolvem alvo preferindo mesma continuidade (`X/Legends` se existir) | "Darth Vader" é redirect pra "Anakin Skywalker" — sem o mapa, arestas apontariam pro vazio |

## Sessão 3 — robustez e processo (2026-07-09, /grill-with-docs)

| # | Galho | Decisão | Racional |
|---|---|---|---|
| 24 | Framework do agente | **LangGraph** supersede Pydantic AI — [ADR-0001](docs/adr/0001-langgraph-over-pydantic-ai.md) | Keyword nº 1 do mercado; fronteira em `agent/` tornou a troca barata |
| 25 | Observabilidade | Langfuse self-hosted no docker-compose; todo run traceado; eval linka regressão → trace | Falha nº 2 do design: sem trace, regressão de eval é caixa-preta |
| 26 | Reprodutibilidade | `corpus.lock` (título, revid) versionado no git — [ADR-0002](docs/adr/0002-corpus-lock.md) | Falha nº 1: evals entre re-crawls não eram comparáveis; fetcher passa a gravar revid |
| 27 | Frontend | Next.js + FastAPI com SSE supersede Streamlit — [ADR-0003](docs/adr/0003-nextjs-fastapi-sse.md). Local-only continua | Aprender front de verdade + tool calls ao vivo na UI |
| 28 | Ruído do grafo | Matriz de compatibilidade de tipo-alvo só nas arestas curadas; cauda de 242 tipos intocada até o eval apontar dano | Poda com evidência, não estética |
| 29 | Processo | Main só via branch+PR+CI+self-review; conventional commits; mini-PRD pra features grandes; golden set e runs como datasets no Langfuse | "Tratar como empresa": história auditável no GitHub e workflow de eval real |
| 30 | Glossário | CONTEXT.md criado (Continuity, Entity, Topic, Chunk, Corpus Lock, Golden Set, Retrieval Strategy, Judge, Baseline); ADRs passam a registrar decisões duras | Vocabulário canônico pro código, docs e eval usarem as mesmas palavras |

## Sessão 4 — estilo OO (2026-07-10, /grill-with-docs)

| # | Galho | Decisão | Racional |
|---|---|---|---|
| 31 | Sequência | Refactor como PR próprio pós-merge da fase 2, 100% preservador de comportamento | Diff de estética separado de diff de comportamento; bisect limpo |
| 32 | Estilo de código | Regras no CLAUDE.md ("Code style") + [ADR-0004](docs/adr/0004-oo-style.md): público=classe/método; injeção estrita com composition root; herança proibida (Protocol; carve-out exceções); polimorfismo só p/ switch repetido; tipos de domínio congelados; ≤4 params | Preferência explícita do dono por OO/composição; sem clean-arch completa (overengineering nesta escala) |
| 33 | Docstrings | Duas classes: LLM-facing (tools de retrieval — obrigatórias, longas, intocáveis) vs internas (mínimas) | As docstrings das tools são prompt engineering — o agente roteia por elas |
| 34 | Polimorfismo | Um único ponto: `EmbeddingProvider` (Protocol) em `core/embeddings.py` | Único type-switch repetido (ingest + query); centralizar mata bug latente de dimensão índice≠query. Rejeitados: Tool objects, estratégias polimórficas (fase 4), reescrever ifs de validação |
| 35 | Pastas | `core/` (folha neutra: domain + embeddings) e `retrieval/` (substitui `tools.py`) | `retrieval` vem do glossário (Retrieval Strategy); `core/` resolve a fronteira ingest↔serving sem arquivos soltos na raiz |
| 36 | Eval: rubrica | Rubrica do Judge v2 fixada ANTES do primeiro Baseline (run 20260710T181909Z): fato extra fundamentado não é alucinação; o corpus vence o conhecimento próprio do Judge; atribuição de continuidade julgada só contra o comportamento esperado | v1 punia respostas corretas (fatos extras) e usava lore de memória contra o grafo; ajustar antes de existir Baseline não move régua junto com objeto — os 90 veredictos foram re-julgados sob uma única rubrica |
| 37 | Eval: runs interrompidas | Run que morre no meio nunca é reportada (sem manifest), mas é retomável com `eval answer --resume <run-id>` — só as respostas faltantes são geradas | O run oficial morreu em 60/90 por rate limit da org (429); descartar 60 respostas pagas re-paga a API sem ganho; o invariante "sem manifest = sem report" continua garantindo números completos |
| 38 | Frontend: conceito | "Watch the agent think" (spec #26): chat + grafo force-directed ao vivo construído dos tool calls via SSE; acumula na sessão; chunks como satélites; nós gêmeos por continuidade; interação nível 1 (sem endpoint novo); react-force-graph-2d; toda tela passa pela skill impeccable | Grilled em 2026-07-10: é o único conceito em que a visualização É a tese do projeto (agente escolhendo estratégia em runtime, visível). Rejeitados: galaxy explorer (hairball, agente vira coadjuvante), eval arena (3x custo), graph-only como produto (overfit no benchmark de 30 perguntas) |
| 39 | Vector store | ~~LanceDB~~ **pgvector** ([ADR-0005](docs/adr/0005-pgvector-over-lancedb.md)): database `holocron` no Postgres do Langfuse (imagem pgvector/pg17), HNSW + cosine, psycopg cru | Postgres+pgvector é o padrão de produção que o mercado reconhece (mesmo racional da #27); o argumento zero-infra do LanceDB morreu quando o compose ganhou Postgres; validado por rodada de eval vs Baseline |
| 36 | Governança | Sem skill nova (decisão #13); skill `add-tool` atualizada para o novo layout | Estilo é restrição permanente (CLAUDE.md), não ritual |

## Risco nº 1

Parse de infobox é mais chato do que parece (templates aninhados, variantes). Se a fase 1 travar: **cortar categorias de artigo, não qualidade do parse** — grafo sujo mata o eval.
