"""Duplicate detection.

Two kinds:
- Exact: identical SHA-1 — byte-for-byte same file.
- Similar: pHash Hamming distance <= threshold — perceptually near-identical
  (burst shots, resize/recompress of the same image, minor crops).

Similar-groups uses transitive clustering via union-find: if A~B and B~C then
A, B, C land in the same group even if A and C themselves differ by more than
`threshold`. That matches what users want when de-duping a burst sequence.

Complexity of find_similar_groups is O(n²) pairwise pHash comparisons. Each
comparison is an int64 XOR + bit_count — ~100–300 ns in CPython — so 26K
files ≈ 338 M pairs ≈ 1–3 min. We sort by pHash first so equal-pHash runs
short-circuit into O(k) union operations and the remaining outer loop is the
main cost.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable


@dataclass
class ExactGroup:
    sha1: str
    ids: list[int]
    count: int
    total_bytes: int


@dataclass
class SimilarGroup:
    ids: list[int]
    count: int


def find_exact_dups(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("""
      SELECT sha1,
             GROUP_CONCAT(id) AS ids,
             COUNT(*) AS n,
             SUM(bytes) AS total
      FROM files
      WHERE sha1 IS NOT NULL AND error IS NULL AND deleted_at IS NULL
      GROUP BY sha1
      HAVING COUNT(*) > 1
      ORDER BY n DESC, total DESC
    """).fetchall()
    return [
        {
            "sha1": r[0],
            "ids": [int(x) for x in r[1].split(",")],
            "count": int(r[2]),
            "total_bytes": int(r[3] or 0),
        }
        for r in rows
    ]


class _UF:
    __slots__ = ("p",)

    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        p = self.p
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def find_similar_groups(
    db: sqlite3.Connection,
    threshold: int = 4,
    progress_every: int = 0,
) -> list[dict]:
    """All files whose pHash Hamming distance is <= threshold cluster via union-find.

    `progress_every` > 0 prints a status line every N outer-loop iterations.
    """
    rows = db.execute("""
      SELECT id, phash FROM files
      WHERE phash IS NOT NULL AND error IS NULL AND deleted_at IS NULL
    """).fetchall()
    if not rows:
        return []

    # Sort by pHash so equal/near-equal hashes are adjacent — we can break early
    # once the Hamming distance grows.
    entries: list[tuple[int, int]] = sorted(
        ((int(r[0]), int(r[1], 16)) for r in rows),
        key=lambda e: e[1],
    )
    n = len(entries)
    uf = _UF(n)

    t0 = time.time()
    for i in range(n):
        h_i = entries[i][1]
        for j in range(i + 1, n):
            h_j = entries[j][1]
            if (h_i ^ h_j).bit_count() <= threshold:
                uf.union(i, j)
        if progress_every and i and i % progress_every == 0:
            rate = i / (time.time() - t0) if time.time() > t0 else 0.0
            remaining = (n - i) / rate if rate else float("inf")
            print(f"[dups-similar] {i}/{n} ({rate:.1f}/s, ETA {remaining:.0f}s)",
                  flush=True)

    # Collect groups by root
    groups: dict[int, list[int]] = {}
    for idx, (file_id, _) in enumerate(entries):
        root = uf.find(idx)
        groups.setdefault(root, []).append(file_id)
    return [
        {"ids": ids, "count": len(ids)}
        for ids in groups.values()
        if len(ids) > 1
    ]
