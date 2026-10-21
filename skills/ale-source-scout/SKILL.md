---
name: ale-source-scout
description: Finds and records evidence-bearing source materials for one AgentHLE candidate, including license and provenance. Use before authoring a document-forensics or data-analysis task.
---

# Source Scout

Produce a source pack that can support a new task of the target subdomain and difficulty. A source
pack is not a set of answers; it is the raw material from which the task and gold will be built.

## Inputs

- Candidate id, stratum, seed anchor, difficulty target
- `profiles/seed_profile.json` (nearest seeds)
- Optional user-provided source directory or URLs

## Outputs

Under `candidates/<id>/`:

- `evidence/sources.jsonl` — one JSON object per line
- `source_pack/` — local copies or excerpts, only when redistribution is allowed
- `candidate.json` — update `source_policy` (`public`, `internal_only`, or `mixed`)

### Source record

```json
{
  "source_id": "src-001",
  "title": "Shanghai Stock Exchange ...",
  "publisher": "Shanghai Stock Exchange",
  "url": "https://...",
  "local_path": "source_pack/src-001.docx",
  "retrieved_at": "2026-10-21T00:00:00Z",
  "published_at": "2023-...",
  "license": "public government document",
  "redistributable": true,
  "sha256": "...",
  "locators": ["section 2.3", "table 1"],
  "notes": "why this source supports the planned task"
}
```

## Rules

1. Prefer authoritative, public, redistributable sources: regulations, public filings, open datasets,
   official documentation.
2. Do not scrape sites whose terms forbid it. Respect robots.txt and rate limits. Do not collect PII.
3. Keep the source pack small enough to bundle as task input. Quote only what the task needs.
4. If a source is not redistributable, set `redistributable: false`, do not copy it into
   `source_pack/`, and mark the candidate `internal_only: true`.
5. Every source must have a stable locator (section, table, page, row range) so the author can record
   exact evidence quotes.
6. Do not collect the answer. If a source happens to contain a direct answer to a planned question,
   either redesign the question or record that tension in `notes`.
7. If no web access is configured, ask the user for a source directory and hash the files. Do not
   fabricate URLs or quotes.

## Stop condition

Scout until the pack can support the planned number of questions and the target difficulty. Then
write `candidate.json` status `SCOUTED` via `python3 -I scripts/state.py set-status <id> SCOUTED`.
