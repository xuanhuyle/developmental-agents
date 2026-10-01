"""Gate-0 worlds (GATE_0_SPEC.md §4): deterministic, in memory, generated from a parameter file.

Nothing under data/world changes. Each *instance* is one question with a catalog that is identical for every member of
its *reveal set*; members differ only in what the triage source reveals:

- template A, "workload reveal": a cheap SQL triage reveals which candidate documents must be read. In member X they
  are the long documents, in member Y the tiny ones (same count, same catalog).
- template B, "dead-branch reveal": a slow memo reveals whether the heaviest work unit is still needed. In member X it
  is discontinued; in member Y the memo names a legacy entity listed in the structured source but without a report in
  the catalog, so every unit with a report stays live.
- D: Experiment 0b's T01 with every region report shortened (same question, same document ids). It is the stage-A
  dissociation state of EXPERIMENT_0C_POSTMORTEM_AND_NEXT_DECISION.md §9, built here only to calibrate it.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from devagents.environment.sources import MAX_ROWS, InformationEnvironment, SourceCosts
from devagents.environment.tasks import TASKS_BY_ID, Route, Task
from devagents.environment.world import COMPANY, REGIONS, World, load_world, region_doc_id
from devagents.runtime.resources import estimate_tokens, to_usd


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------- catalog


class G0Info(InformationEnvironment):
    """The unchanged information environment, with the catalog's table and title lines supplied per instance. The
    catalog text has exactly the base format (sources.InformationEnvironment.catalog)."""

    def __init__(self, world: World, costs: SourceCosts, titles: dict[str, str], schema: tuple[str, ...]):
        super().__init__(world, costs)
        self.titles = dict(titles)
        self.schema = tuple(schema)

    def catalog(self) -> str:
        c = self.costs
        lines = [
            f'Structured source "sql": SQLite, read-only SELECT queries. Fee ${to_usd(c.sql_fee):.4f} per query; '
            f"latency {c.sql_base_s:g}s + {c.sql_per_row_s:g}s per returned row (max {MAX_ROWS} rows). Tables:",
            *[f"  - {s}" for s in self.schema],
            f"Unstructured documents: fee ${to_usd(c.doc_fee):.4f} per document; latency {c.doc_base_s:g}s + "
            f"{c.doc_per_token_s:g}s per document token. The full text enters the reader's context. Documents:",
        ]
        for doc_id in sorted(self.world.docs):
            lines.append(f"  - {doc_id}: {self.titles.get(doc_id, doc_id)} (~{self.doc_tokens[doc_id]} tokens)")
        return "\n".join(lines)


# --------------------------------------------------------------------------- data model


@dataclass(frozen=True)
class Member:
    key: str  # "X" | "Y" | "D"
    world: World
    answer: str
    needed: tuple[str, ...]  # documents that must be read, besides the triage source
    live_units: tuple[int, ...]  # indices into Instance.units of the units that are needed
    reveal: str  # what the triage source shows this member (must differ between members)


@dataclass(frozen=True)
class Instance:
    id: str  # "A1", "B2", "D"
    template: str  # "A" | "B" | "D"
    question: str
    kind: str  # grading kind: "number" | "name"
    titles: tuple  # ((doc_id, title), ...); empty: the base catalog (0b titles and schema)
    schema: tuple[str, ...]
    triage: tuple  # (("sql", query),) | (("doc", memo_id),) | ()
    units: tuple[tuple[str, ...], ...]  # candidate work units (document tuples), in catalog order
    members: tuple[Member, ...]
    triage_filters_units: bool  # A: a child can run the triage itself and skip units that are not needed
    base_task: str = ""  # D: the 0b task it is a twin of

    @property
    def task_id(self) -> str:
        return TASKS_BY_ID[self.base_task].id if self.base_task else f"G0-{self.id}"

    def task(self, member: Member) -> Task:
        """The runtime's Task. The id, question and kind are the same for every member; only the graded answer
        differs. `routes` is informational (the runtime never reads it)."""
        if self.base_task:
            return TASKS_BY_ID[self.base_task]
        return Task(self.task_id, "gate0", self.template, self.question, member.answer, self.kind, (member.answer,),
                    (Route(sql=tuple(t for k, t in self.triage if k == "sql"), docs=member.needed,
                           docs_depend_on_sql=bool(self.triage)),))

    def info(self, member: Member, costs: SourceCosts) -> InformationEnvironment:
        if not self.titles:
            return InformationEnvironment(member.world, costs)
        return G0Info(member.world, costs, dict(self.titles), self.schema)

    @property
    def unit_docs(self) -> tuple[str, ...]:
        return tuple(d for u in self.units for d in u)

    def digest(self) -> str:
        """Content hash of everything any agent could ever read in any member, plus the graded answers."""
        return sha256_text(canonical({
            "id": self.id, "template": self.template, "question": self.question, "kind": self.kind,
            "titles": list(self.titles), "schema": list(self.schema), "triage": [list(t) for t in self.triage],
            "units": [list(u) for u in self.units], "base_task": self.base_task,
            "members": [{"key": m.key, "answer": m.answer, "needed": list(m.needed), "live": list(m.live_units),
                         "sql": sha256_text(m.world.sql_script),
                         "docs": {d: sha256_text(t) for d, t in sorted(m.world.docs.items())}} for m in self.members],
        }))


# --------------------------------------------------------------------------- deterministic filler

_SUBJ = ["The review team", "The regional office", "Field engineers", "The quality office", "Procurement",
         "The planning desk", "Finance", "The operations lead", "The audit group", "Site management", "The service desk",
         "Engineering", "The logistics team", "The compliance office", "The account team"]
_VERB = ["noted that", "confirmed that", "recorded that", "reported that", "observed that", "agreed that",
         "flagged that", "documented that", "summarised that", "checked that"]
_OBJ = ["scheduling changes were absorbed without delays", "the shared calendar removed double bookings",
        "spare parts arrived within the agreed window", "training hours stayed in line with the guideline",
        "the checklist pilot received positive feedback", "freight costs rose after a carrier surcharge",
        "the lease discussion is still ongoing", "warranty claims showed no systemic issue",
        "cycle counts remained within tolerance", "the helpdesk saw a brief rise in tickets",
        "the safety committee closed all open actions", "forecast sharing reduced expedite requests",
        "the handover was documented in full", "the second-source plan is under review",
        "packaging changes reduced transit damage", "engineering change notices were approved faster",
        "the survey response rate improved slightly", "travel was kept to the approved minimum",
        "the backlog was cleared before month end", "new hires completed their induction on time"]


def _sentence(key: str, i: int) -> str:
    h = hashlib.sha256(f"{key}|{i}".encode()).digest()
    return f"{_SUBJ[h[0] % len(_SUBJ)]} {_VERB[h[1] % len(_VERB)]} {_OBJ[h[2] % len(_OBJ)]}."


def _pad(head: str, tail: str, key: str, target_tokens: int) -> str:
    """head + filler sentences + tail, with filler added until the estimated size reaches target_tokens."""
    body, i = [], 0
    while estimate_tokens(head + " ".join(body) + tail) < target_tokens:
        body.append(_sentence(key, i))
        i += 1
    return head + " ".join(body) + tail


def _values(key: str, n: int, lo: int, hi: int, step: int) -> list[int]:
    """n distinct deterministic multiples of `step` in [lo, hi]."""
    out, i = [], 0
    while len(out) < n:
        h = int.from_bytes(hashlib.sha256(f"{key}|v{i}".encode()).digest()[:4], "big")
        v = lo + (h % ((hi - lo) // step + 1)) * step
        if v not in out:
            out.append(v)
        i += 1
    return out


def _sql_rows(sql_script: str, query: str) -> str:
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql_script)
    rows = conn.execute(query).fetchall()
    conn.close()
    return "\n".join(" | ".join(str(v) for v in r) for r in rows)


# --------------------------------------------------------------------------- template A: workload reveal

A_DOMAINS = {
    "incident": dict(entity="INC", doc="incident", title="Incident report {e}", table="incidents",
                     id_col="incident_id", other_col="site", flag=("open", "closed"),
                     fact="estimated repair cost", prev="initial triage estimate",
                     question="Among the incidents whose status is 'open' in the incidents table, what is the highest "
                              "estimated repair cost given in their incident reports? Answer with the amount in US "
                              "dollars, as a number.",
                     others=["Ostrava depot", "Gdansk yard", "Linz plant", "Brno depot", "Turku yard", "Aarhus plant"]),
    "audit": dict(entity="AUD", doc="audit", title="Supplier audit file {e}", table="audits", id_col="audit_id",
                  other_col="supplier", flag=("escalated", "routine"), fact="corrective-action cost",
                  prev="provisional estimate",
                  question="Among the audits whose status is 'escalated' in the audits table, what is the highest "
                           "corrective-action cost recorded in their audit files? Answer with the amount in US "
                           "dollars, as a number.",
                  others=["Halvorsen Tooling", "Mirecourt Alloys", "Tessaly Polymers", "Okafor Castings",
                          "Brandvold Seals", "Quintero Optics"]),
    "account": dict(entity="ACC", doc="account", title="Client account review {e}", table="accounts",
                    id_col="account_id", other_col="region", flag=("at_risk", "stable"), fact="contract value at risk",
                    prev="value at risk reported last quarter",
                    question="Among the accounts whose status is 'at_risk' in the accounts table, what is the highest "
                             "contract value at risk stated in their account reviews? Answer with the amount in US "
                             "dollars, as a number.",
                    others=["North", "South", "East", "West", "Central", "Coastal"]),
}


def build_a(p: dict) -> Instance:
    d = A_DOMAINS[p["domain"]]
    n, first = p["n_candidates"], p["first_number"]
    ents = [f"{d['entity']}-{first + i}" for i in range(n)]
    docs_ids = [f"{d['doc']}-{first + i}" for i in range(n)]
    long_idx = [i for i in range(n) if i % 2 == 0]  # interleaved in catalog order
    tiny_idx = [i for i in range(n) if i % 2 == 1]
    vals = _values(f"{p['id']}|cost", n, 12_000, 98_000, 100)
    prev = _values(f"{p['id']}|prev", n, 10_000, 99_000, 100)
    docs = {}
    for i, (e, doc_id) in enumerate(zip(ents, docs_ids)):
        other = d["others"][i % len(d["others"])]
        fact = (f"The {d['fact']} is ${vals[i]:,}; the {d['prev']} of ${prev[i]:,} has been superseded.")
        if i in long_idx:
            head = (f"# {d['title'].format(e=e)}\n\nFile maintained by {COMPANY}. "
                    f"{d['other_col'].capitalize()}: {other}.\n\n## Assessment\n")
            k = f"{p['id']}|{doc_id}"
            body = _pad("", "", k + "|a", p["long_tokens"] // 2)
            docs[doc_id] = _pad(head + body + " " + fact + "\n\n## Notes\n", "\n", k + "|b", p["long_tokens"])
        else:
            docs[doc_id] = (f"# {d['title'].format(e=e)}\n\n{d['other_col'].capitalize()}: {other}. {fact}\n")
            docs[doc_id] = _pad(docs[doc_id], "", f"{p['id']}|{doc_id}|t", p["tiny_tokens"])
    titles = tuple((doc_id, d["title"].format(e=e)) for e, doc_id in zip(ents, docs_ids))
    schema = (f"{d['table']}({d['id_col']}, {d['other_col']}, status)  -- status is '{d['flag'][0]}' or "
              f"'{d['flag'][1]}'",)
    triage_sql = f"SELECT {d['id_col']} FROM {d['table']} WHERE status = '{d['flag'][0]}' ORDER BY {d['id_col']}"
    members = []
    for key, idx in (("X", long_idx), ("Y", tiny_idx)):
        stmts = [f"CREATE TABLE {d['table']} ({d['id_col']} TEXT NOT NULL, {d['other_col']} TEXT NOT NULL, "
                 f"status TEXT NOT NULL);"]
        for i, e in enumerate(ents):
            status = d["flag"][0] if i in idx else d["flag"][1]
            other = d["others"][i % len(d["others"])].replace("'", "''")
            stmts.append(f"INSERT INTO {d['table']} VALUES ('{e}', '{other}', '{status}');")
        sql = "\n".join(stmts) + "\n"
        world = World(sql_script=sql, docs=dict(docs))
        members.append(Member(key, world, str(max(vals[i] for i in idx)), tuple(docs_ids[i] for i in idx),
                              tuple(idx), _sql_rows(sql, triage_sql)))
    return Instance(p["id"], "A", d["question"], "number", titles, schema, (("sql", triage_sql),),
                    tuple((x,) for x in docs_ids), tuple(members), triage_filters_units=True)


# --------------------------------------------------------------------------- template B: dead-branch reveal

B_DOMAINS = {
    "lines": dict(doc="line", title="Product line report: {u}", memo="portfolio-memo",
                  memo_title="Portfolio review memo 2025", table="lines", cols=("name", "segment"),
                  fact="Warranty cost in 2025-Q3 came to ${v}k, against ${p}k in 2025-Q2.",
                  dead="The following product lines were discontinued in 2025 and are excluded from all current "
                       "reporting: {names}. All other product lines remain active.",
                  question="Considering only the product lines that the portfolio review memo lists as active, what "
                           "was the highest warranty cost in 2025-Q3, in thousands of US dollars? Answer with the "
                           "number."),
    "tracks": dict(doc="track", title="Research track report: {u}", memo="steering-memo",
                   memo_title="Programme steering memo", table="tracks", cols=("name", "sponsor"),
                   fact="The remaining budget requirement is ${v}k; the plan of record had ${p}k.",
                   dead="The steering group closed the following research tracks: {names}. All other research "
                        "tracks continue.",
                   question="Considering only the research tracks that the programme steering memo lists as "
                            "continuing, what is the largest remaining budget requirement, in thousands of US "
                            "dollars? Answer with the number."),
    "bids": dict(doc="bid", title="Vendor bid dossier: {u}", memo="shortlist-memo",
                 memo_title="Procurement shortlist memo", table="vendors", cols=("name", "country"),
                 fact="The total bid price is ${v}k; the indicative price was ${p}k.",
                 dead="The following vendors were eliminated from the tender: {names}. All other vendors remain "
                      "shortlisted.",
                 question="Considering only the vendors that the procurement shortlist memo keeps in the tender, "
                          "what is the highest total bid price, in thousands of US dollars? Answer with the number."),
}


def build_b(p: dict) -> Instance:
    d = B_DOMAINS[p["domain"]]
    heavy, lights, phantom = p["heavy"], p["lights"], p["phantom"]
    if len(phantom) != len(heavy[0]):
        raise ValueError("the phantom name must have the heavy unit's length, so both memos have one size")
    units = [heavy] + list(lights)  # unit 0 is the heavy unit
    names = [u[0] for u in units]
    vals = sorted(_values(f"{p['id']}|val", len(units), 300, 990, 1), reverse=True)  # the heavy unit has the max
    prevs = _values(f"{p['id']}|prev", len(units), 250, 990, 1)
    docs, titles = {}, []
    for i, (name, tokens) in enumerate(units):
        doc_id = f"{d['doc']}-{name.lower()}"
        head = f"# {d['title'].format(u=name)}\n\nPrepared for {COMPANY}.\n\n## Summary\n"
        k = f"{p['id']}|{doc_id}"
        body = _pad("", "", k + "|a", tokens // 2)
        docs[doc_id] = _pad(head + body + " " + d["fact"].format(v=vals[i], p=prevs[i]) + "\n\n## Detail\n", "\n",
                            k + "|b", tokens)
        titles.append((doc_id, d["title"].format(u=name)))
    titles.append((d["memo"], d["memo_title"]))
    unit_ids = [f"{d['doc']}-{n.lower()}" for n in names]
    # The phantom is a real entity of the structured source with no report in the catalog (a legacy line, track or
    # vendor), so member Y's memo names something the agent can look up; it has no bearing on the answer.
    sql = (f"CREATE TABLE {d['table']} ({', '.join(c + ' TEXT NOT NULL' for c in d['cols'])});\n"
           + "".join(f"INSERT INTO {d['table']} VALUES ('{n}', 'core');\n" for n in names)
           + f"INSERT INTO {d['table']} VALUES ('{phantom}', 'legacy');\n")
    members = []
    for key, dead, live in (("X", [heavy[0]], list(range(1, len(units)))), ("Y", [phantom], list(range(len(units))))):
        head = f"# {d['memo_title']}\n\nIssued by the {COMPANY} programme office.\n\n"
        mk = f"{p['id']}|memo"
        pre = _pad("", "", mk + "|a", p["memo_tokens"] // 2)
        memo = _pad(head + pre + " " + d["dead"].format(names=", ".join(dead)) + "\n\n", "\n", mk + "|b",
                    p["memo_tokens"])
        world = World(sql_script=sql, docs={**docs, d["memo"]: memo})
        members.append(Member(key, world, str(max(vals[i] for i in live)), tuple(unit_ids[i] for i in live),
                              tuple(live), memo))
    if len(members[0].world.docs[d["memo"]]) != len(members[1].world.docs[d["memo"]]):
        raise ValueError("the memos of a reveal set must have identical length")
    return Instance(p["id"], "B", d["question"], "number", tuple(titles), (f"{d['table']}({', '.join(d['cols'])})",),
                    (("doc", d["memo"]),),
                    tuple((u,) for u in unit_ids), tuple(members), triage_filters_units=False)


# --------------------------------------------------------------------------- D: the shortened T01 twin


def short_region_doc(region: str) -> str:
    r = REGIONS[region]
    return (f"# {COMPANY} — {region} region: quarterly summary, 2025-Q3\n\nRegional manager: {r['manager']}. Revenue "
            f"${r['rev']['2025-Q3'] / 1000:.3f} million (2025-Q2: ${r['rev']['2025-Q2'] / 1000:.3f} million). Customer "
            f"churn {r['churn_q3']:.1f}% (2025-Q2: {r['churn_q2']:.1f}%). Headcount {r['hc_start']} at the start of "
            f"the quarter and {r['hc_end']} at the end.\n")


def build_d(p: dict) -> Instance:
    base = load_world()
    task = TASKS_BY_ID[p["base_task"]]
    docs = dict(base.docs)
    regions = [r for r in REGIONS]
    for r in regions:
        docs[region_doc_id(r)] = short_region_doc(r)
    world = World(sql_script=base.sql_script, docs=docs)
    route_docs = tuple(sorted(task.routes[0].docs))
    member = Member("D", world, task.answer, route_docs, tuple(range(len(route_docs))), "")
    return Instance("D", "D", task.question, task.kind, (), (), (), tuple((x,) for x in route_docs), (member,),
                    triage_filters_units=False, base_task=p["base_task"])


BUILDERS = {"A": build_a, "B": build_b, "D": build_d}


def build_instances(candidates: dict) -> list[Instance]:
    """Build every instance of a candidate-set file ({"instances": [{"template": ..., ...}, ...]})."""
    return [BUILDERS[p["template"]](p) for p in candidates["instances"]]
