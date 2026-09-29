"""Information access with explicit, measurable costs.

Structured access (SQL) is cheap and fast and returns compact results. Unstructured access
(a document) costs a fee plus processing latency proportional to its length, and puts the
whole text into the agent's context, which the agent then pays for on every later LLM step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from devagents.environment.world import DOC_TITLES, SQL_SCHEMA_SUMMARY, World
from devagents.runtime.resources import estimate_tokens, to_usd, usd

SQL_SOURCE = "sql"
MAX_ROWS = 50


@dataclass(frozen=True)
class SourceCosts:
    sql_fee: int = usd(0.0005)
    sql_base_s: float = 1.0
    sql_per_row_s: float = 0.02
    doc_fee: int = usd(0.002)
    doc_base_s: float = 3.0
    doc_per_token_s: float = 0.1  # unstructured processing is slow (SPEC §3.1); a calibration knob (§7.4)


@dataclass
class QueryResult:
    source: str  # "sql" or a doc id
    kind: str  # "structured" | "unstructured"
    ok: bool
    text: str
    tokens: int
    rows: int
    fee: int  # µ$
    latency_s: float
    error: str = ""


class InformationEnvironment:
    def __init__(self, world: World, costs: SourceCosts = SourceCosts()):
        self.world = world
        self.costs = costs
        self._conn = world.connect()
        self.doc_tokens = {d: estimate_tokens(t) for d, t in world.docs.items()}

    @property
    def source_ids(self) -> frozenset[str]:
        return frozenset({SQL_SOURCE, *self.world.docs})

    def catalog(self) -> str:
        c = self.costs
        lines = [
            f'Structured source "sql": SQLite, read-only SELECT queries. Fee ${to_usd(c.sql_fee):.4f} per query; '
            f"latency {c.sql_base_s:g}s + {c.sql_per_row_s:g}s per returned row (max {MAX_ROWS} rows). Tables:",
            *[f"  - {s}" for s in SQL_SCHEMA_SUMMARY],
            f"Unstructured documents: fee ${to_usd(c.doc_fee):.4f} per document; latency {c.doc_base_s:g}s + "
            f"{c.doc_per_token_s:g}s per document token. The full text enters the reader's context. Documents:",
        ]
        for doc_id in sorted(self.world.docs):
            lines.append(f"  - {doc_id}: {DOC_TITLES.get(doc_id, doc_id)} (~{self.doc_tokens[doc_id]} tokens)")
        return "\n".join(lines)

    def query(self, kind: str, target: str) -> QueryResult:
        if kind == "doc":
            return self._read_doc(target)
        if kind == "sql":
            return self._run_sql(target)
        return QueryResult(target, "?", False, "", 0, 0, 0, 0.0, f"unknown request kind {kind!r}")

    def _read_doc(self, doc_id: str) -> QueryResult:
        c = self.costs
        if doc_id not in self.world.docs:
            return QueryResult(doc_id, "unstructured", False, "", 0, 0, 0, 0.0, f"unknown document {doc_id!r}")
        text = self.world.docs[doc_id]
        tokens = self.doc_tokens[doc_id]
        return QueryResult(doc_id, "unstructured", True, text, tokens, 0, c.doc_fee,
                           c.doc_base_s + tokens * c.doc_per_token_s)

    def _run_sql(self, sql: str) -> QueryResult:
        c = self.costs
        if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
            return QueryResult(SQL_SOURCE, "structured", False, "", 0, 0, 0, 0.0, "only SELECT queries are allowed")
        try:
            cur = self._conn.execute(sql)
            rows = cur.fetchmany(MAX_ROWS + 1)
        except Exception as exc:  # sqlite3 errors are data for the agent, still charged
            return QueryResult(SQL_SOURCE, "structured", False, "", 0, 0, c.sql_fee, c.sql_base_s, f"SQL error: {exc}")
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        header = " | ".join(d[0] for d in cur.description or [])
        body = "\n".join(" | ".join(_fmt(v) for v in row) for row in rows)
        text = f"{header}\n{body}" + ("\n(truncated)" if truncated else "")
        return QueryResult(SQL_SOURCE, "structured", True, text, estimate_tokens(text), len(rows), c.sql_fee,
                           c.sql_base_s + len(rows) * c.sql_per_row_s)


def _fmt(v) -> str:
    return f"{v:.6g}" if isinstance(v, float) else str(v)
