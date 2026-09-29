"""Task suite, pilot tasks and resource regimes (SPEC §4).

Each ground truth is *computed* from the world's fact tables. `task_class`, `subtype` and
`routes` are used only by evaluation and calibration. The acting agent sees only the neutral
id and the question.
"""

from __future__ import annotations

from dataclasses import dataclass

from devagents.environment.world import (
    AS_OF, AUDITS, REGIONS, SUPPLIERS, TRAVEL_POLICY, region_doc_id, supplier_doc_id,
)


@dataclass(frozen=True)
class Route:
    """One minimal way to answer: SQL statements and/or documents to read. For a dependent route,
    `candidates` is the full set of documents the SQL result selects `docs` from."""
    sql: tuple[str, ...] = ()
    docs: tuple[str, ...] = ()
    docs_depend_on_sql: bool = False
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    id: str
    task_class: str  # "solo" (A) | "parallel" (B) | "cross" (C)   -- never shown to the agent
    subtype: str  # "" | "dependent" | "shortcut" (class C only)
    question: str
    answer: str
    kind: str  # "number" | "name"
    aliases: tuple[str, ...]
    routes: tuple[Route, ...]

    @property
    def max_doc_route(self) -> int:
        return max(len(r.docs) for r in self.routes)


@dataclass(frozen=True)
class Regime:
    name: str
    budget_usd: float
    deadline_s: float
    value_of_time: float  # $ per simulated second
    task_value: float = 1.0  # V
    failure_penalty: float = 1.0


# Regimes differ ONLY in value_of_time (SPEC §4). The constants are provisional until
# `python -m devagents freeze` writes data/frozen.json; SPEC §7.4 lists the only knobs gate repair may move.
DEADLINE_S = 1500.0
BUDGET_USD = 1.00
TASK_VALUE = 0.50  # V: $ value of a correct answer
REGIMES = {
    "relaxed": Regime("relaxed", budget_usd=BUDGET_USD, deadline_s=DEADLINE_S, value_of_time=0.00005, task_value=TASK_VALUE),
    "urgent": Regime("urgent", budget_usd=BUDGET_USD, deadline_s=DEADLINE_S, value_of_time=0.0008, task_value=TASK_VALUE),
}

Q3 = "2025-Q3"
RATE_Q3_SQL = ("SELECT s.name, a.defects * 1.0 / a.units_inspected AS rate FROM audits a JOIN suppliers s "
               "USING (supplier_id) WHERE a.quarter = '2025-Q3' ORDER BY rate DESC")


def _rate(sid: int, q: str = Q3) -> float:
    units, defects = AUDITS[sid][q]
    return defects / units


def _unique_best(values: dict, reverse: bool) -> object:
    ranked = sorted(values, key=values.get, reverse=reverse)
    assert values[ranked[0]] != values[ranked[1]], "argmax/argmin must be unique"
    return ranked[0]


def _sup_aliases(sid: int) -> tuple[str, ...]:
    return (SUPPLIERS[sid]["name"], SUPPLIERS[sid]["name"].split()[0])


def _build_tasks() -> list[Task]:
    regions = tuple(region_doc_id(r) for r in REGIONS)
    suppliers = tuple(supplier_doc_id(s) for s in SUPPLIERS)

    s4_total = sum(AUDITS[s][Q3][1] for s in AUDITS)
    p1 = _unique_best({r: REGIONS[r]["churn_q3"] for r in REGIONS}, reverse=True)
    p2 = sum(1 for s in SUPPLIERS.values() if s["iso9001"][0] == "valid" and s["iso9001"][1] >= AS_OF)
    p3 = sum(r["hc_end"] for r in REGIONS.values())
    p4 = _unique_best({s: SUPPLIERS[s]["founded"] for s in SUPPLIERS}, reverse=False)
    c1 = _unique_best({s: _rate(s) for s in SUPPLIERS}, reverse=True)
    c3_set = [s for s in SUPPLIERS if _rate(s) > 0.015]
    c3 = _unique_best({s: SUPPLIERS[s]["plant_opened"] for s in c3_set}, reverse=False)
    c4_set = [r for r in REGIONS if REGIONS[r]["rev"][Q3] > 3900]
    c4 = _unique_best({r: REGIONS[r]["churn_q3"] for r in c4_set}, reverse=False)
    d1 = _unique_best({r: REGIONS[r]["rev"][Q3] for r in REGIONS}, reverse=True)
    d2 = sum(1 for r in REGIONS.values() if r["rev"][Q3] > 4000)
    d3_countries = ("United Kingdom", "Ireland", "Canada")
    d3 = sum(1 for s in SUPPLIERS.values() if s["country"] in d3_countries)
    c5_set = [s for s in SUPPLIERS if AUDITS[s][Q3][0] > 6000]
    c5 = _unique_best({s: SUPPLIERS[s]["plant_opened"] for s in c5_set}, reverse=True)
    assert len(c3_set) == 6 and len(c4_set) == 5 and len(c5_set) == 6
    # each filter must matter: the unfiltered answer differs
    assert c3 != _unique_best({s: SUPPLIERS[s]["plant_opened"] for s in SUPPLIERS}, reverse=False)
    assert c4 != _unique_best({r: REGIONS[r]["churn_q3"] for r in REGIONS}, reverse=False)
    assert c5 != _unique_best({s: SUPPLIERS[s]["plant_opened"] for s in SUPPLIERS}, reverse=True)

    return [
        # ---- class B: facts exist only in documents
        Task("T01", "parallel", "", "Across the six regions, which reported the highest customer churn rate in 2025-Q3? "
             "Answer with the region name.", p1, "name", (p1,), (Route(docs=regions),)),
        Task("T04", "parallel", "", f"Across the eight suppliers, how many held a valid ISO 9001 certificate as of {AS_OF}? "
             "Answer with a number.", str(p2), "number", (), (Route(docs=suppliers),)),
        Task("T07", "parallel", "", "Across the six regions, what was the total headcount at the end of 2025-Q3? "
             "Answer with a number.", str(p3), "number", (), (Route(docs=regions),)),
        Task("T10", "parallel", "", "Across the eight suppliers, which was founded earliest? Answer with the supplier name.",
             SUPPLIERS[p4]["name"], "name", _sup_aliases(p4), (Route(docs=suppliers),)),
        # ---- class A
        Task("T02", "solo", "", "Under the current travel and expenses policy, what is the maximum hotel reimbursement per "
             "night for international travel, in US dollars? Answer with a number.",
             str(TRAVEL_POLICY["intl_hotel_cap"]), "number", (), (Route(docs=("travel-policy",)),)),
        Task("T05", "solo", "", "How many defects were recorded for the supplier Calloway Metals in 2025-Q2? "
             "Answer with a number.", str(AUDITS[2]["2025-Q2"][1]), "number", (),
             (Route(sql=("SELECT a.defects FROM audits a JOIN suppliers s USING (supplier_id) "
                         "WHERE s.name = 'Calloway Metals' AND a.quarter = '2025-Q2'",)),)),
        Task("T08", "solo", "", "In which city is the supplier Fenwright Circuits headquartered? Answer with the city name.",
             SUPPLIERS[5]["city"], "name", (SUPPLIERS[5]["city"],), (Route(docs=(supplier_doc_id(5),)),)),
        Task("T11", "solo", "", "What was the total number of defects recorded across all suppliers in 2025-Q3? "
             "Answer with a number.", str(s4_total), "number", (),
             (Route(sql=("SELECT SUM(defects) FROM audits WHERE quarter = '2025-Q3'",)),)),
        # ---- class C, dependent: the SQL result determines which documents are needed
        Task("T03", "cross", "dependent", "Which supplier had the highest defect rate (defects divided by units inspected) "
             "in 2025-Q3, and who is that supplier's current CEO? Answer with the CEO's full name.",
             SUPPLIERS[c1]["ceo"], "name", (SUPPLIERS[c1]["ceo"],),
             (Route(sql=(RATE_Q3_SQL,), docs=(supplier_doc_id(c1),), docs_depend_on_sql=True, candidates=suppliers),)),
        Task("T09", "cross", "dependent", "Among suppliers whose 2025-Q3 defect rate (defects divided by units inspected) "
             "exceeded 1.5%, which one's main production plant opened earliest? Answer with the supplier name.",
             SUPPLIERS[c3]["name"], "name", _sup_aliases(c3),
             (Route(sql=(RATE_Q3_SQL,), docs=tuple(supplier_doc_id(s) for s in c3_set), docs_depend_on_sql=True,
                    candidates=suppliers),)),
        Task("T12", "cross", "dependent", "Among regions whose 2025-Q3 revenue exceeded $3.9 million, which reported the "
             "lowest customer churn rate in 2025-Q3? Answer with the region name.", c4, "name", (c4,),
             (Route(sql=("SELECT region FROM regional_revenue WHERE quarter = '2025-Q3' AND revenue_kusd > 3900",),
                    docs=tuple(region_doc_id(r) for r in c4_set), docs_depend_on_sql=True, candidates=regions),
              Route(docs=regions))),  # the region reports also state revenue
        Task("T15", "cross", "dependent", "Among suppliers that inspected more than 6,000 units in 2025-Q3, which one's "
             "main production plant opened most recently? Answer with the supplier name.",
             SUPPLIERS[c5]["name"], "name", _sup_aliases(c5),
             (Route(sql=("SELECT s.name, a.units_inspected FROM audits a JOIN suppliers s USING (supplier_id) "
                         "WHERE a.quarter = '2025-Q3' AND a.units_inspected > 6000",),
                    docs=tuple(supplier_doc_id(s) for s in c5_set), docs_depend_on_sql=True, candidates=suppliers),)),
        # ---- class C, shortcut: same template as class B, but one SQL query suffices (facts also in the docs)
        Task("T06", "cross", "shortcut", "Across the six regions, which reported the highest revenue in 2025-Q3? "
             "Answer with the region name.", d1, "name", (d1,),
             (Route(sql=("SELECT region, revenue_kusd FROM regional_revenue WHERE quarter = '2025-Q3' "
                         "ORDER BY revenue_kusd DESC",)), Route(docs=regions))),
        Task("T13", "cross", "shortcut", "Across the six regions, how many reported revenue above $4.0 million in 2025-Q3? "
             "Answer with a number.", str(d2), "number", (),
             (Route(sql=("SELECT COUNT(*) FROM regional_revenue WHERE quarter = '2025-Q3' AND revenue_kusd > 4000",)),
              Route(docs=regions))),
        Task("T14", "cross", "shortcut", "Across the eight suppliers, how many are based in the United Kingdom, Ireland or "
             "Canada? Answer with a number.", str(d3), "number", (),
             (Route(sql=("SELECT COUNT(*) FROM suppliers WHERE country IN ('United Kingdom', 'Ireland', 'Canada')",)),
              Route(docs=suppliers))),
    ]


def _build_pilot_tasks() -> list[Task]:
    """Held out from the main suite; used only by the pilot (single and central modes)."""
    x2_region = _unique_best({r: REGIONS[r]["hc_end"] for r in REGIONS}, reverse=False)
    x3 = _unique_best({s: AUDITS[s]["2025-Q2"][0] for s in SUPPLIERS}, reverse=True)
    return [
        Task("X1", "solo", "", "Under the current travel and expenses policy, what is the daily meal allowance for "
             "international travel, in US dollars? Answer with a number.", str(TRAVEL_POLICY["per_diem_intl"]),
             "number", (), (Route(docs=("travel-policy",)),)),
        Task("X2", "parallel", "", "Across the six regions, who manages the region with the smallest headcount at the end "
             "of 2025-Q3? Answer with the manager's full name.", REGIONS[x2_region]["manager"], "name",
             (REGIONS[x2_region]["manager"],), (Route(docs=tuple(region_doc_id(r) for r in REGIONS)),)),
        Task("X3", "cross", "dependent", "Which supplier inspected the most units in 2025-Q2, and who is its current CEO? "
             "Answer with the CEO's full name.", SUPPLIERS[x3]["ceo"], "name", (SUPPLIERS[x3]["ceo"],),
             (Route(sql=("SELECT s.name, a.units_inspected FROM audits a JOIN suppliers s USING (supplier_id) "
                         "WHERE a.quarter = '2025-Q2' ORDER BY a.units_inspected DESC",),
                    docs=(supplier_doc_id(x3),), docs_depend_on_sql=True),)),
    ]


TASKS: list[Task] = sorted(_build_tasks(), key=lambda t: t.id)
PILOT_TASKS: list[Task] = _build_pilot_tasks()
TASKS_BY_ID = {t.id: t for t in TASKS + PILOT_TASKS}
