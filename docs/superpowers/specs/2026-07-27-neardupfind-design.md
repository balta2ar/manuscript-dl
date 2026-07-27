# neardupfind — design

## Purpose

Read filenames from stdin (like `dupfind`), detect *near*-duplicate files whose
content overlap is at least `--sim` (Jaccard over content-defined chunks), print
the newer members of each near-dup group, and retain the oldest. Catches
re-saved / re-OCR'd PDFs that byte-exact tools such as `dupfind` miss (e.g. the
same scan reprocessed by different OCRmyPDF versions, differing only in
header/xref/metadata bytes while 99.9% of the body is identical).

## Interface

Mirrors `dupfind`:

- **stdin:** filenames, one per line (e.g. from `fd -t f -e pdf`).
- **stdout:** newer near-dup paths, one per line (plain).
- **stderr:** skip warnings; with `-o`, retained originals (green if TTY).

Flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `-o`, `--show-original` | off | Print retained original (oldest mtime) per group to stderr. |
| `--size FLOAT` | `0.01` | Size gate: skip comparing files whose sizes differ by more than this fraction. |
| `--sim FLOAT` | `0.98` | Minimum **exact** Jaccard to report a pair as near-duplicate. |
| `--inc BYTES` | `1048576` (1 MiB) | Progressive read increment per round. Accepts plain bytes or suffixes (e.g. `1M`, `512K`). |

## Algorithm

### 1. Ingest
`stat` each stdin path. Skip non-files and stat errors (warn to stderr, matching
`dupfind`). Record `(path, size, mtime)`.

### 2. Size gate (per-pair, two-pointer)
Sort by size. A candidate relationship exists only between files whose sizes are
within `+size` fraction of each other. This is **non-transitive** — transitive
chaining was measured to over-cluster catastrophically (a single chain of 1,155
of 1,933 files at 1%). A file with no size-neighbour is dropped immediately and
never read.

Measured effect on the target library (1,933 PDFs): naive all-pairs ≈ 1.87M →
**12,865** candidate pairs at 1%.

### 3. Progressive rounds (hybrid LSH + safe upper bound)
Read live files in `--inc` increments. Each round a file is opened, its next
increment is read at the correct offset, then closed — files are **not** held
open across rounds, so peak file descriptors equal the parallelism degree, not
the cluster size.

Per round, for each live file:
- Extend its accumulated FastCDC chunk set (SHA-1 chunk IDs) with the new bytes.
- Update its MinHash signature over the accumulated chunk set.

Then:
- **LSH bucket** all live files on their accumulated signatures. The LSH internal
  threshold is set **looser** than `--sim` (e.g. 0.8) to over-include candidates
  and avoid MinHash false-negatives dropping true dupes.
- **Discard gate (bucket-collision + upper-bound safety):** a file stays live if
  it shares an LSH bucket with ≥1 other file. If it is alone in all its buckets,
  it is discarded only if its optimistic upper bound to its best-ever
  bucket-mate is already `< sim`. The upper bound assumes every remaining unread
  byte on both sides becomes a matching chunk; it can only be too lenient, never
  too strict, so a true near-dupe is never dropped early. Otherwise the file is
  kept for one more round (guards against early header/prefix divergence, e.g.
  the Senja files differing in their first ~3.7 KB `/Linearized` header).
- A file whose bytes are exhausted stops advancing but remains available for
  confirmation.

Continue until no live file has unread bytes, or all remaining live files are
bucket singletons.

### 4. Exact confirmation
For files that co-bucketed, compute the **exact** Jaccard on their full
accumulated chunk sets. Pairs `≥ --sim` become real near-dup edges. This removes
MinHash false positives from the output.

### 5. Grouping (union-find)
Confirmed edges are unioned into connected components; each component is a
near-dup group. Singletons are dropped. Near-dup similarity is not perfectly
transitive; if `(A,B)` and `(B,C)` confirm but `(A,C)` does not, union-find still
groups all three — consistent with `dupfind`'s "keep oldest, print the rest".

### 6. Output
Per group, sort by `(mtime, path)`; retain the oldest, print the rest to stdout.
With `-o`, print the retained original to stderr (green if TTY).

## Structure

Compact, composable functions with single responsibilities and clean interfaces
(no incidental comments):

- `parse_size(str) -> int` — byte-size arg parser (`1M`, `512K`, plain int).
- `stat_inputs(lines) -> list[Entry]` — ingest + stat, warn-and-skip.
- `size_candidates(entries, size) -> pairs / neighbour index` — two-pointer gate.
- `Chunker` — wraps `fastcdc`, yields the accumulated chunk set for a file given
  a byte range; reusable for both progressive and exact passes.
- `Signature` — thin wrapper over `datasketch.MinHash` (update, jaccard).
- `upper_bound(matched, union, remaining_bytes, avg_chunk) -> float`.
- `progressive_filter(entries, inc, sim) -> co_bucketed` — the round loop.
- `confirm(co_bucketed, sim) -> edges` — exact Jaccard.
- `group(edges) -> components` — union-find.
- `report(groups, show_original)` — output, oldest-retained.
- `main()` — wires stdin → gate → progressive → confirm → group → report.

## Libraries

- `fastcdc` — content-defined chunking (gear-hash FastCDC).
- `hashlib` (stdlib) — SHA-1 chunk IDs.
- `datasketch` — `MinHash`, `MinHashLSH`.

Parallelism across cores for per-round read + chunk. In-memory only; no disk
cache.

## Validation (on the real target library)

- Size gate: 1.87M naive pairs → 12,865 at 1%.
- Two different ~80 MB PDFs: discarded after the first 1 MB (upper bound
  0.975 < 0.98) — ~160× I/O saving vs reading in full.
- Senja trio (`Lita språklæra …`, sizes 29,230,906 / …911 / …912 — within 1%,
  differ only in header/xref/metadata): co-bucket after 1 MB (estimated Jaccard
  0.938–0.977) and confirm as a near-dup group; `dupfind` (SHA-256) never
  detects them.

## Known limitations (noted, not handled)

- A size-cluster of hundreds of mutually-near-identical files still incurs heavy
  within-bucket exact confirmation (≈ O(k²) for that cluster). Acceptable for
  real libraries; a leader-based reduction could be added later if needed.
- LSH is probabilistic; the loose-threshold + exact-confirm design keeps output
  correct, but pathological inputs could still cost extra reads.

## Non-goals

- Positional / streaming byte comparison (headers always differ — rejected).
- Text extraction or rendering-based comparison.
- Deletion (prints names only, like `dupfind`).
- Disk-cached persistent index.
