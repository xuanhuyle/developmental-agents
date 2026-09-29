"""Ground truth is derivable from the committed sources, and the committed world matches its generator."""

import re

from devagents.environment.sources import InformationEnvironment
from devagents.environment.tasks import PILOT_TASKS, TASKS, TASKS_BY_ID
from devagents.environment.world import (
    AUDITS, REGIONS, SUPPLIERS, TRAVEL_POLICY, WORLD_DIR, load_world, region_doc_id, render_docs, render_sql, supplier_doc_id,
)
from devagents.evals.metrics import grade

WORLD = load_world()
ENV = InformationEnvironment(WORLD)


def test_committed_world_matches_generator():
    assert (WORLD_DIR / "structured.sql").read_text() == render_sql()
    assert WORLD.docs == render_docs()


def test_every_fact_used_by_a_task_appears_in_its_source():
    for r, f in REGIONS.items():
        doc = WORLD.docs[region_doc_id(r)]
        assert f"churn for the quarter came in at {f['churn_q3']:.1f}%" in doc
        assert f"ended it with {f['hc_end']} employees" in doc
        assert f"${f['rev']['2025-Q3'] / 1000:.3f} million" in doc
    for sid, s in SUPPLIERS.items():
        doc = WORLD.docs[supplier_doc_id(sid)]
        for fact in (f"founded in {s['founded']}", f"headquartered in {s['city']}, {s['country']}",
                     f"opened in {s['plant_opened']}", f"chief executive officer is {s['ceo']}"):
            assert fact in doc
        status, date = s["iso9001"]
        assert (f"valid until {date}" if status == "valid" else f"expired on {date}") in doc
    assert f"up to ${TRAVEL_POLICY['intl_hotel_cap']} per night" in WORLD.docs["travel-policy"]


def test_sql_routes_return_the_ground_truth():
    def first_row(sql):
        res = ENV.query("sql", sql)
        assert res.ok, res.error
        return res.text.splitlines()[1].split(" | ")
    assert first_row(TASKS_BY_ID["T05"].routes[0].sql[0]) == ["171"]
    assert first_row(TASKS_BY_ID["T11"].routes[0].sql[0]) == [TASKS_BY_ID["T11"].answer]
    assert first_row(TASKS_BY_ID["T06"].routes[0].sql[0])[0] == TASKS_BY_ID["T06"].answer
    assert first_row(TASKS_BY_ID["T13"].routes[0].sql[0]) == [TASKS_BY_ID["T13"].answer]
    assert first_row(TASKS_BY_ID["T14"].routes[0].sql[0]) == [TASKS_BY_ID["T14"].answer]
    # dependent routes: the SQL selects exactly the route's documents
    t09 = ENV.query("sql", TASKS_BY_ID["T09"].routes[0].sql[0]).text
    names = [line.split(" | ")[0] for line in t09.splitlines()[1:]]
    assert len(names) == 8  # all rates; the filter is in the question (> 1.5%)
    t15 = ENV.query("sql", TASKS_BY_ID["T15"].routes[0].sql[0]).text.splitlines()[1:]
    assert {supplier_doc_id(next(i for i, s in SUPPLIERS.items() if s["name"] == l.split(" | ")[0])) for l in t15} \
        == set(TASKS_BY_ID["T15"].routes[0].docs)


def test_filters_matter_and_answers_are_unique():
    rate = {s: AUDITS[s]["2025-Q3"][1] / AUDITS[s]["2025-Q3"][0] for s in SUPPLIERS}
    assert len(set(rate.values())) == len(rate)
    assert len({r["churn_q3"] for r in REGIONS.values()}) == len(REGIONS)
    assert len({s["founded"] for s in SUPPLIERS.values()}) == len(SUPPLIERS)
    assert len({s["plant_opened"] for s in SUPPLIERS.values()}) == len(SUPPLIERS)


def test_task_ids_and_texts_do_not_reveal_the_class():
    for t in TASKS + PILOT_TASKS:
        assert re.fullmatch(r"[TX]\d\d|X\d", t.id)
        for word in ("parallel", "solo", "cross", "shortcut", "dependent", "spawn", "agent"):
            assert not re.search(rf"\b{word}\b", t.question.lower()), (t.id, word)


def test_grading_is_exact_but_tolerant_of_formatting():
    t_num, t_name = TASKS_BY_ID["T11"], TASKS_BY_ID["T10"]
    assert grade(t_num, "1,565") == grade(t_num, "1565 defects") == 1.0
    assert grade(t_num, "1565 or 1566") == 0.0 and grade(t_num, "1564") == 0.0 and grade(t_num, None) == 0.0
    assert grade(t_name, "Galloway Fasteners") == grade(t_name, "galloway") == grade(t_name, "The Galloway Fasteners.") == 1.0
    assert grade(t_name, "Ivel Coatings") == 0.0


def test_sql_is_read_only():
    res = ENV.query("sql", "DELETE FROM suppliers")
    assert not res.ok and "only SELECT" in res.error
    res = ENV.query("sql", "WITH x AS (SELECT 1) DELETE FROM suppliers")
    assert not res.ok
    assert ENV.query("sql", "SELECT COUNT(*) FROM suppliers").text.splitlines()[1] == "8"
