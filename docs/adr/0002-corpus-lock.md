# ADR-0002: Corpus pinned by a lockfile of revision ids

The wiki changes daily, so eval runs over re-crawled data are not comparable —
and the raw data (~300MB) is too big to commit. We record a `corpus.lock`
manifest of (page title, revid) in git; rebuilds fetch each page at its exact
pinned revision via the MediaWiki API. Alternatives rejected: tarball as a
GitHub Release asset (blob outside git history, breakable link) and
crawl-date-only stamping (doesn't actually make runs comparable).

**Consequence:** the fetcher must request and store revision ids, and a full
rebuild from the lock refetches ~6k pages (~40 min) instead of downloading one
blob.
