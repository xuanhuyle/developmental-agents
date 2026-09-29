"""Deterministic synthetic world: one fictional company with structured and unstructured sources.

The fact tables below are the single source of truth. `render_sql()` and `render_docs()` turn
them into the committed files under data/world/ (regenerate with `python -m devagents
build-world`). Ground-truth answers in tasks.py are computed from these facts, never typed in.

Documents deliberately bury each fact in filler prose next to plausible distractors (prior-quarter
values, a different ISO standard, a former CEO, a secondary site) so that extracting the fact
requires actually reading the document.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

WORLD_DIR = Path(__file__).resolve().parents[2] / "data" / "world"
AS_OF = "2025-10-01"
COMPANY = "Varnholt Instruments"

# --------------------------------------------------------------------------- facts

REGIONS = {
    # name: revenue k$ by quarter, churn % (Q2, Q3), headcount (start, end of Q3), manager
    "Northland": dict(rev={"2025-Q1": 4550, "2025-Q2": 5150, "2025-Q3": 4820}, churn_q2=2.8, churn_q3=3.1,
                      hc_start=138, hc_end=142, manager="Ilse Marwood"),
    "Eastmarch": dict(rev={"2025-Q1": 3880, "2025-Q2": 4020, "2025-Q3": 3950}, churn_q2=3.5, churn_q3=2.2,
                      hc_start=101, hc_end=97, manager="Tomasz Adeyemi"),
    "Southvale": dict(rev={"2025-Q1": 4990, "2025-Q2": 5105, "2025-Q3": 5310}, churn_q2=4.3, churn_q3=4.6,
                      hc_start=160, hc_end=168, manager="Rhea Lindqvist"),
    "Westreach": dict(rev={"2025-Q1": 4310, "2025-Q2": 4380, "2025-Q3": 4475}, churn_q2=4.1, churn_q3=5.3,
                      hc_start=119, hc_end=121, manager="Dario Okonkwo"),
    "Midlands": dict(rev={"2025-Q1": 3940, "2025-Q2": 3990, "2025-Q3": 4105}, churn_q2=2.6, churn_q3=2.9,
                     hc_start=112, hc_end=110, manager="Priya Castellanos"),
    "Coastal": dict(rev={"2025-Q1": 3710, "2025-Q2": 3700, "2025-Q3": 3620}, churn_q2=2.4, churn_q3=1.8,
                    hc_start=84, hc_end=86, manager="Bram Oyelaran"),
}

SUPPLIERS = {
    # id: facts. iso9001 = (status, date); "valid" means valid until date, "expired" means expired on date.
    1: dict(name="Brisk Components", country="Germany", component="connectors", city="Dortmund",
            second_site="Bochum", founded=1987, plant_opened=2004, ceo="Helga Brandt", former_ceo="Otto Kessler",
            iso9001=("valid", "2026-11-30"), iso14001=("expired", "2024-09-30")),
    2: dict(name="Calloway Metals", country="United Kingdom", component="housings", city="Sheffield",
            second_site="Rotherham", founded=1962, plant_opened=1999, ceo="Martin Pryce", former_ceo="Alan Whitcombe",
            iso9001=("valid", "2027-03-31"), iso14001=("valid", "2026-06-30")),
    3: dict(name="Dunmore Plastics", country="Ireland", component="enclosures", city="Limerick",
            second_site="Ennis", founded=1994, plant_opened=2011, ceo="Siobhan Keane", former_ceo="Declan Rourke",
            iso9001=("expired", "2025-06-30"), iso14001=("valid", "2027-01-31")),
    4: dict(name="Eskerfield Optics", country="Sweden", component="sensors", city="Uppsala",
            second_site="Västerås", founded=2003, plant_opened=2015, ceo="Anders Holm", former_ceo="Lena Varg",
            iso9001=("valid", "2026-08-31"), iso14001=("expired", "2025-03-31")),
    5: dict(name="Fenwright Circuits", country="Netherlands", component="circuit boards", city="Eindhoven",
            second_site="Tilburg", founded=1979, plant_opened=2001, ceo="Joost van Dael", former_ceo="Marijke Smit",
            iso9001=("valid", "2027-01-31"), iso14001=("valid", "2026-10-31")),
    6: dict(name="Galloway Fasteners", country="Canada", component="fasteners", city="Hamilton",
            second_site="Guelph", founded=1958, plant_opened=1997, ceo="Renée Tremblay", former_ceo="George Mackie",
            iso9001=("expired", "2025-02-28"), iso14001=("expired", "2024-12-31")),
    7: dict(name="Harrow Sensors", country="United States", component="sensors", city="Dayton",
            second_site="Columbus", founded=2011, plant_opened=2018, ceo="Keisha Monroe", former_ceo="Paul Deering",
            iso9001=("valid", "2026-05-31"), iso14001=("valid", "2026-09-30")),
    8: dict(name="Ivel Coatings", country="France", component="coatings", city="Lyon",
            second_site="Grenoble", founded=1971, plant_opened=1990, ceo="Camille Rousseau", former_ceo="Jean Morel",
            iso9001=("valid", "2026-12-31"), iso14001=("expired", "2025-05-31")),
}

AUDITS = {
    # supplier_id: {quarter: (units_inspected, defects)}
    1: {"2025-Q1": (11500, 190), "2025-Q2": (11800, 199), "2025-Q3": (12000, 204)},
    2: {"2025-Q1": (7800, 150), "2025-Q2": (8100, 171), "2025-Q3": (8000, 184)},
    3: {"2025-Q1": (9000, 210), "2025-Q2": (9200, 240), "2025-Q3": (9500, 266)},
    4: {"2025-Q1": (3900, 90), "2025-Q2": (4100, 101), "2025-Q3": (4000, 132)},
    5: {"2025-Q1": (14500, 180), "2025-Q2": (14800, 190), "2025-Q3": (15000, 195)},
    6: {"2025-Q1": (19500, 350), "2025-Q2": (19800, 362), "2025-Q3": (20000, 380)},
    7: {"2025-Q1": (4800, 88), "2025-Q2": (4900, 97), "2025-Q3": (5000, 106)},
    8: {"2025-Q1": (6800, 95), "2025-Q2": (6900, 99), "2025-Q3": (7000, 98)},
}

TRAVEL_POLICY = dict(intl_hotel_cap=240, domestic_hotel_cap=180, previous_intl_cap=210, per_diem_intl=85,
                     per_diem_domestic=60, effective="2025-07-01")


def region_doc_id(region: str) -> str:
    return f"region-{region.lower()}"


def supplier_doc_id(sid: int) -> str:
    return f"supplier-{SUPPLIERS[sid]['name'].split()[0].lower()}"


# --------------------------------------------------------------------------- structured source

def render_sql() -> str:
    lines = [
        f"-- {COMPANY} structured data (synthetic). Generated by devagents/environment/world.py.",
        "CREATE TABLE suppliers (supplier_id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL, component TEXT NOT NULL);",
        "CREATE TABLE audits (supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id), quarter TEXT NOT NULL, units_inspected INTEGER NOT NULL, defects INTEGER NOT NULL);",
        "CREATE TABLE regional_revenue (region TEXT NOT NULL, quarter TEXT NOT NULL, revenue_kusd INTEGER NOT NULL);",
    ]
    for sid, s in SUPPLIERS.items():
        lines.append(f"INSERT INTO suppliers VALUES ({sid}, '{s['name']}', '{s['country']}', '{s['component']}');")
    for sid, quarters in AUDITS.items():
        for q, (units, defects) in quarters.items():
            lines.append(f"INSERT INTO audits VALUES ({sid}, '{q}', {units}, {defects});")
    for region, r in REGIONS.items():
        for q, rev in r["rev"].items():
            lines.append(f"INSERT INTO regional_revenue VALUES ('{region}', '{q}', {rev});")
    return "\n".join(lines) + "\n"


SQL_SCHEMA_SUMMARY = [
    "suppliers(supplier_id, name, country, component)",
    "audits(supplier_id, quarter, units_inspected, defects)  -- quarters '2025-Q1'..'2025-Q3'",
    "regional_revenue(region, quarter, revenue_kusd)  -- revenue in thousands of USD",
]

# --------------------------------------------------------------------------- unstructured sources

_FILLER = {
    "region": [
        "The regional team completed the migration of its field-service scheduling to the shared planning calendar, which removed a recurring source of double bookings.",
        "Training hours per employee were broadly in line with the company guideline, with most sessions focused on the updated calibration procedures.",
        "Warehouse cycle counts were performed on schedule and variances remained within the tolerance agreed with the finance office.",
        "Several long-standing accounts renewed their service contracts, although a few asked for shorter terms while they reassess capital budgets.",
        "The team piloted a new ticket triage checklist; early feedback from technicians was positive, and the checklist will be reviewed again next quarter.",
        "Freight costs were affected by a carrier surcharge introduced mid-quarter, which the logistics desk is renegotiating.",
        "Two technicians completed the advanced metrology certificate, bringing the number of certified staff in the region to a comfortable level.",
        "Customer satisfaction surveys were distributed to a rotating sample of accounts, and response rates improved slightly after the reminder emails were shortened.",
        "The office lease discussion is ongoing; facilities expects a decision before the end of the fiscal year.",
        "A small number of warranty claims were escalated to the central quality team for root-cause analysis; none indicated a systemic issue.",
        "Sales engineers held joint visits with distributor partners to present the updated instrument range and the extended calibration plans.",
        "The regional safety committee met twice and closed all open actions from the previous inspection.",
        "Spare-parts availability improved after the central depot adjusted reorder points for fast-moving items.",
        "IT rolled out the new laptop image to the regional staff, and the helpdesk reported a modest increase in tickets during the first week.",
    ],
    "supplier": [
        "The supplier participates in the quarterly business review with procurement and has generally been responsive to corrective-action requests.",
        "Lead times were stable over the review period, with occasional delays attributed to upstream raw-material allocation.",
        "Packaging was redesigned last year to reduce damage in transit, and receiving inspection has noted fewer dented cartons since then.",
        "The account manager changed in the spring; the handover was documented and no open issues were lost.",
        "Payment terms remain at the company standard, and there are no outstanding disputes with accounts payable.",
        "The supplier has been asked to provide a second-source plan for its most critical subcomponents as part of the resilience program.",
        "On-site visits by the supplier-quality engineers found housekeeping and traceability practices to be adequate.",
        "Engineering change notices are exchanged through the shared portal, and turnaround on approvals has improved.",
        "The supplier's sustainability questionnaire was received and is under review by the environmental compliance office.",
        "Forecast sharing now happens monthly, which has reduced the number of expedite requests from the planning team.",
        "Sample inspections for the latest product revision passed first-article approval after one round of minor dimensional corrections.",
        "The supplier indicated interest in a longer framework agreement, which procurement will evaluate during annual sourcing.",
    ],
}


def _pick_filler(kind: str, key: str, n: int) -> list[str]:
    """Deterministic, platform-independent selection of n distinct filler sentences."""
    pool = _FILLER[kind]
    ranked = sorted(pool, key=lambda s: hashlib.sha256(f"{key}|{s}".encode()).hexdigest())
    return ranked[:n]


def _region_doc(region: str) -> str:
    r = REGIONS[region]
    f = _pick_filler("region", region, 10)
    rev_q3 = r["rev"]["2025-Q3"] / 1000
    rev_q2 = r["rev"]["2025-Q2"] / 1000
    incident = (
        "In August a burst water main flooded part of the regional warehouse; stock was relocated within two days and insurance claims are in progress. "
        if region == "Westreach" else ""
    )
    return f"""# {COMPANY} — {region} region: quarterly report, 2025-Q3

Prepared by the {region} regional office. Regional manager: {r['manager']}.

## Overview
{f[0]} {f[1]} The quarter closed with regional revenue of ${rev_q3:.3f} million, compared with ${rev_q2:.3f} million in the previous quarter. {f[2]}

## Customers
{f[3]} {f[4]} Customer churn for the quarter came in at {r['churn_q3']:.1f}%, after {r['churn_q2']:.1f}% in 2025-Q2; the regional target remains below 3.0%. {f[5]}

## People
{f[6]} The region started the quarter with {r['hc_start']} employees and ended it with {r['hc_end']} employees, after planned transfers and a small number of new hires. {f[7]}

## Operations
{incident}{f[8]} {f[9]}

## Outlook
The regional plan for the next quarter emphasises service-contract renewals and continued attention to response times. Figures in this report are preliminary until confirmed by the central finance team.
"""


def _supplier_doc(sid: int) -> str:
    s = SUPPLIERS[sid]
    f = _pick_filler("supplier", s["name"], 8)
    status, date = s["iso9001"]
    iso9001 = (f"Its ISO 9001 quality-management certificate is valid until {date}."
               if status == "valid" else
               f"Its ISO 9001 quality-management certificate expired on {date} and has not yet been renewed; a recertification audit is being scheduled.")
    s14, d14 = s["iso14001"]
    iso14001 = (f"The ISO 14001 environmental certificate is valid until {d14}."
                if s14 == "valid" else f"The ISO 14001 environmental certificate lapsed on {d14}.")
    return f"""# Supplier profile: {s['name']}

Supplier-management file maintained by {COMPANY} procurement. Status as of {AS_OF}.

## Company
{s['name']} supplies {s['component']} to {COMPANY}. The company was founded in {s['founded']} and is headquartered in {s['city']}, {s['country']}; its main production plant, located in {s['second_site']}, opened in {s['plant_opened']}. {f[0]} {f[1]}

## Leadership
The current chief executive officer is {s['ceo']}, who succeeded {s['former_ceo']}. {f[2]} {f[3]}

## Certifications
{iso14001} {f[4]} {iso9001} {f[5]}

## Relationship notes
{f[6]} {f[7]}
"""


def _travel_policy_doc() -> str:
    p = TRAVEL_POLICY
    return f"""# {COMPANY} — Travel and expenses policy

Effective {p['effective']}. This version replaces the policy dated 2023-01-01.

## Scope
This policy applies to all employees and contractors travelling on company business. Travel must be approved in advance by the budget holder, and bookings should be made through the corporate travel portal wherever possible.

## Transport
Economy class is the default for flights under six hours. Rail is preferred over air for journeys under four hours door to door. Rental cars require a business justification, and fuel must be refilled before return to avoid surcharges.

## Accommodation
Domestic hotel stays are reimbursed up to ${p['domestic_hotel_cap']} per night. For international travel, hotel stays are reimbursed up to ${p['intl_hotel_cap']} per night; under the previous policy the international cap was ${p['previous_intl_cap']}. Stays above the cap require written pre-approval from a director. Loyalty points may be retained by the employee.

## Meals and per diem
Meals are covered by a daily allowance of ${p['per_diem_domestic']} for domestic travel and ${p['per_diem_intl']} for international travel. Alcohol is not reimbursable except at approved client events.

## Claims
Expense claims must be submitted within 30 days of return with itemised receipts. Claims submitted late may be rejected. Questions about this policy should be directed to the finance office.
"""


def render_docs() -> dict[str, str]:
    docs = {"travel-policy": _travel_policy_doc()}
    for region in REGIONS:
        docs[region_doc_id(region)] = _region_doc(region)
    for sid in SUPPLIERS:
        docs[supplier_doc_id(sid)] = _supplier_doc(sid)
    return docs


DOC_TITLES = {
    "travel-policy": "Travel and expenses policy",
    **{region_doc_id(r): f"{r} region quarterly report 2025-Q3" for r in REGIONS},
    **{supplier_doc_id(s): f"Supplier profile: {SUPPLIERS[s]['name']}" for s in SUPPLIERS},
}

# --------------------------------------------------------------------------- files


def write_world(directory: Path = WORLD_DIR) -> None:
    directory = Path(directory)
    (directory / "docs").mkdir(parents=True, exist_ok=True)
    (directory / "structured.sql").write_text(render_sql(), encoding="utf-8")
    for doc_id, text in render_docs().items():
        (directory / "docs" / f"{doc_id}.md").write_text(text, encoding="utf-8")


@dataclass
class World:
    sql_script: str
    docs: dict[str, str]

    def connect(self) -> sqlite3.Connection:
        """Fresh in-memory, read-only database built from the committed SQL script."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.executescript(self.sql_script)
        conn.execute("PRAGMA query_only = ON")
        return conn


def load_world(directory: Path = WORLD_DIR) -> World:
    directory = Path(directory)
    docs = {p.stem: p.read_text(encoding="utf-8") for p in sorted((directory / "docs").glob("*.md"))}
    return World(sql_script=(directory / "structured.sql").read_text(encoding="utf-8"), docs=docs)
