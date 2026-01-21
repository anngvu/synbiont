#!/usr/bin/env python3
"""Convert the Sage governance spreadsheet into a Turtle module."""

import argparse
import json
import pathlib
import re
import sys
import unicodedata
from typing import Dict, List, Optional

import pandas as pd

DEFAULT_INPUT = pathlib.Path("reference/DataTypes-brief-Sept2025.xlsx")
DEFAULT_OUTPUT = pathlib.Path("ontology/modules/governance_sage_ref.ttl")
PROPERTY_ORDER = [
    ("Identifiability risks", "sagegov:identifiabilityRisk"),
    ("Access Level", "sagegov:accessLevel"),
    ("Description", "dct:description"),
    ("Capabilities", "sagegov:capabilities"),
    ("Examples", "sagegov:example"),
    ("Downloadable data", "sagegov:downloadable"),
    ("Redistribution", "sagegov:redistribution"),
    ("Affiliation Requirement", "sagegov:affiliationRequirement"),
    ("Synapse Account", "sagegov:synapseAccountRequirement"),
    ("Human Subjects Training", "sagegov:humanSubjectsTraining"),
    ("Data Access Request", "sagegov:dataAccessRequest"),
    ("Data Use Certificate Signed by Signing Official", "sagegov:dataUseCertificate"),
    ("General description of research objectives (posted)", "sagegov:researchObjectiveRequirement"),
    ("Proof of IRB approval", "sagegov:irbApproval"),
    ("Technical environment security standards", "sagegov:securityRequirements"),
    ("Approval Process", "sagegov:approvalProcess"),
]
BOOLEAN_FIELDS = {
    "Downloadable data",
    "Redistribution",
    "Affiliation Requirement",
    "Synapse Account",
    "Human Subjects Training",
    "Data Access Request",
    "Data Use Certificate Signed by Signing Official",
    "General description of research objectives (posted)",
    "Proof of IRB approval",
}
HEADER_ROWS = {
    "Access Prerequisites",
    "Request Submission and Approval Steps",
}
INTERNAL_COLUMN_KEY = "__column_index__"
DATA_TYPE_COLUMNS: set[int] = set()
ALSO_DATA_LABELS = {"hipaa safe harbor"}
ROW5_DATA_KEY = "__row5_data"
ROW4_DATA_KEY = "__row4_data"
ACCESS_LEVEL_NOTE_PRED = "sagegov:accessLevelNote"
VALUE_STRINGS_TO_SKIP = {
    "** with some exceptions at data contributors discretion",
    "** with some exceptions at data contributor's discretion",
}
ACCESS_LEVEL_DEFS = {
    "AnonymousOrOpen": {
        "label": "Anonymous / Open",
        "comment": "Data is usable without registration or affiliation.",
    },
    "Registered": {
        "label": "Registered",
        "comment": "Data usage requires a Synapse account but not additional governance approvals.",
    },
    "RestrictedLimited": {
        "label": "Restricted / Limited",
        "comment": "Data usage limited by contributor-defined contract terms.",
    },
    "Controlled": {
        "label": "Controlled",
        "comment": "Data potentially re-identifiable and subject to access review.",
    },
    "Enclave": {
        "label": "Enclave",
        "comment": "Sensitive data that must remain inside a secure compute enclave.",
    },
}
ACCESS_LEVEL_LOOKUP = {
    re.sub(r"[^a-z0-9]+", "", meta["label"].lower()): term
    for term, meta in ACCESS_LEVEL_DEFS.items()
}
IDENTIFIABILITY_RISK_DEFS = {
    "LowIdentifiabilityRisk": {
        "label": "Low",
        "comment": "Data has low likelihood of re-identification.",
    },
    "SomeIdentifiabilityRisk": {
        "label": "Some risks",
        "comment": "Data could, in certain contexts, be used to re-identify individuals.",
    },
    "HighIdentifiabilityRisk": {
        "label": "High",
        "comment": "Data is likely to re-identify individuals if misused.",
    },
}
IDENTIFIABILITY_RISK_LOOKUP = {
    re.sub(r"[^a-z0-9]+", "", meta["label"].lower()): term
    for term, meta in IDENTIFIABILITY_RISK_DEFS.items()
}
RESERVED_IDENTIFIERS = set(ACCESS_LEVEL_DEFS.keys()) | set(IDENTIFIABILITY_RISK_DEFS.keys())
SOURCE_NOTE = "reference/DataTypes-brief-Sept2025.xlsx"
PREFIX_BLOCK = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix sagegov: <https://synapse.org/synbiont/governance/> .
"""
CLASS_BLOCK = """
sagegov:AccessProfile a owl:Class ;
  rdfs:label "Sage governance access profile" ;
  rdfs:comment "Profiles derived from the Sage governance reference spreadsheet." .

sagegov:Data a owl:Class ;
  rdfs:label "Sage data type" ;
  rdfs:comment "Data classifications referenced in governance policies." .

sagegov:AccessLevel a owl:Class ;
  rdfs:label "Access level" ;
  rdfs:comment "Permitted usage tiers for Synapse data." .

sagegov:IdentifiabilityRisk a owl:Class ;
  rdfs:label "Identifiability risk" ;
  rdfs:comment "Relative likelihood that data could be used to re-identify individuals." .

sagegov:AccessProfileRule a owl:Class ;
  rdfs:label "Governance rule" ;
  rdfs:comment "Helper class for constraints referenced inside the governance module." ;
  rdfs:isDefinedBy sagegov:AccessProfile ."""


def camel_case_identifier(value: str, seen: Dict[str, int]) -> str:
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", value.strip()) if p]
    if not parts:
        base = "Profile"
    else:
        chunked: List[str] = []
        for p in parts:
            if p.isupper():
                chunked.append(p)
            else:
                chunked.append(p[0].upper() + p[1:].lower())
        base = "".join(chunked)
    if base in RESERVED_IDENTIFIERS:
        base = f"{base}Profile"
    if base[0].isdigit():
        base = f"Profile{base}"
    count = seen.get(base, 0)
    if count:
        new_id = f"{base}{count+1}"
        seen[base] = count + 1
        return new_id
    seen[base] = 1
    return base


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip()


def ascii_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def normalize_label_text(value: str) -> str:
    text = normalize_text(value)
    return re.sub(r"\s+", " ", text)


def literal(value: str) -> str:
    cleaned = ascii_text(normalize_text(value))
    return json.dumps(cleaned)


def normalize_bool(value: str) -> Optional[bool]:
    collapsed = normalize_text(value).rstrip("*").strip()
    lowered = collapsed.lower()
    if lowered in {"yes", "y", "true"}:
        return True
    if lowered in {"no", "n", "false"}:
        return False
    return None


def format_value(label: str, value: str) -> str:
    if label in BOOLEAN_FIELDS:
        as_bool = normalize_bool(value)
        if as_bool is not None:
            return "true" if as_bool else "false"
    return literal(value)


def access_level_term(value: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())
    return ACCESS_LEVEL_LOOKUP.get(normalized)


def access_level_defs_block() -> str:
    pieces: List[str] = []
    for term, meta in ACCESS_LEVEL_DEFS.items():
        pieces.append(f"sagegov:{term} a skos:Concept, sagegov:AccessLevel ;")
        pieces.append(f"  skos:prefLabel {literal(meta['label'])} ;")
        if meta.get("comment"):
            pieces.append(f"  rdfs:comment {literal(meta['comment'])} ;")
        pieces[-1] = pieces[-1].rstrip(" ;") + " .\n"
    return "".join(pieces)


def identifiability_risk_term(value: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())
    return IDENTIFIABILITY_RISK_LOOKUP.get(normalized)


def identifiability_risk_defs_block() -> str:
    pieces: List[str] = []
    for term, meta in IDENTIFIABILITY_RISK_DEFS.items():
        pieces.append(f"sagegov:{term} a skos:Concept, sagegov:IdentifiabilityRisk ;")
        pieces.append(f"  skos:prefLabel {literal(meta['label'])} ;")
        if meta.get("comment"):
            pieces.append(f"  rdfs:comment {literal(meta['comment'])} ;")
        pieces[-1] = pieces[-1].rstrip(" ;") + " .\n"
    return "".join(pieces)


def collect_profiles(df) -> List[Dict[str, List[str]]]:
    row_labels = df.iloc[:, 0].ffill().apply(lambda v: normalize_text(v) if not pd.isna(v) else v)
    data_type_rows = [idx for idx, label in enumerate(row_labels) if label == "Data Type"]
    row4_idx = data_type_rows[0] if data_type_rows else None
    row5_idx = data_type_rows[1] if len(data_type_rows) > 1 else None
    profiles: List[Dict[str, List[str]]] = []
    for col in range(1, df.shape[1]):
        series = df.iloc[:, col]
        bucket: Dict[str, List[str]] = {}
        has_row5_data = False
        has_row4_data = False
        for row_idx, (label, raw_value) in enumerate(zip(row_labels, series)):
            if pd.isna(label) or label in HEADER_ROWS:
                continue
            if pd.isna(raw_value):
                continue
            label_key = label.strip()
            value_text = normalize_text(raw_value)
            if not value_text:
                continue
            normalized_skip = value_text.replace("'", "").replace('"', '').lower()
            if normalized_skip in VALUE_STRINGS_TO_SKIP:
                continue
            bucket.setdefault(label_key, []).append(value_text)
            if label_key == "Data Type" and row5_idx is not None and row_idx == row5_idx:
                has_row5_data = True
            if label_key == "Data Type" and row4_idx is not None and row_idx == row4_idx:
                has_row4_data = True
        if any(bucket.values()):
            bucket[INTERNAL_COLUMN_KEY] = col
            if has_row5_data:
                bucket[ROW5_DATA_KEY] = True
            if has_row4_data:
                bucket[ROW4_DATA_KEY] = True
            profiles.append(bucket)
    return profiles


def build_turtle(profiles: List[Dict[str, List[str]]]) -> str:
    header_blocks = [
        PREFIX_BLOCK.strip(),
        CLASS_BLOCK.strip(),
        access_level_defs_block().strip(),
        identifiability_risk_defs_block().strip(),
        "",
    ]
    lines = [block for block in header_blocks if block]
    seen_ids: Dict[str, int] = {}
    for profile in profiles:
        names = [normalize_label_text(name) for name in profile.get("Data Type", [])]
        if not names:
            access_level_values = profile.get("Access Level", [])
            if access_level_values:
                names = [normalize_label_text(access_level_values[0])]
        if not names:
            continue
        pref_label = names[0]
        alt_labels = [name for name in names[1:] if name != pref_label]
        node_id = camel_case_identifier(pref_label, seen_ids)
        col_idx = profile.get(INTERNAL_COLUMN_KEY)
        is_data = False
        if DATA_TYPE_COLUMNS and col_idx is not None:
            is_data = col_idx in DATA_TYPE_COLUMNS
        is_data = is_data or bool(profile.get(ROW4_DATA_KEY)) or bool(profile.get(ROW5_DATA_KEY))
        if profile.get(ROW5_DATA_KEY):
            is_data = True
        classes: List[str] = ["skos:Concept"]
        if is_data:
            classes.append("sagegov:Data")
        else:
            classes.append("sagegov:AccessProfile")
        if normalize_label_text(pref_label).lower() in ALSO_DATA_LABELS:
            if "sagegov:Data" not in classes:
                classes.append("sagegov:Data")
            if "sagegov:AccessProfile" not in classes:
                classes.append("sagegov:AccessProfile")
        entry_lines = [
            f"sagegov:{node_id} a {', '.join(classes)} ;",
            f"  skos:prefLabel {literal(pref_label)} ;",
        ]
        for alt in alt_labels:
            entry_lines.append(f"  skos:altLabel {literal(alt)} ;")
        wrote_access_level = False
        for label, predicate in PROPERTY_ORDER:
            values = profile.get(label, [])
            if not values:
                continue
            if label == "Access Level":
                wrote_access_level = True
                canonical_written = False
                canonical_index: Optional[int] = None
                for idx, value in enumerate(values):
                    term = access_level_term(value)
                    if term:
                        entry_lines.append(f"  {predicate} sagegov:{term} ;")
                        canonical_written = True
                        canonical_index = idx
                        break
                if not canonical_written:
                    for value in values:
                        entry_lines.append(f"  {predicate} {literal(value)} ;")
                else:
                    for idx, value in enumerate(values):
                        if idx == canonical_index:
                            continue
                        entry_lines.append(f"  {ACCESS_LEVEL_NOTE_PRED} {literal(value)} ;")
                continue
            if label == "Identifiability risks":
                for value in values:
                    term = identifiability_risk_term(value)
                    if term:
                        entry_lines.append(f"  {predicate} sagegov:{term} ;")
                    else:
                        entry_lines.append(f"  {predicate} {literal(value)} ;")
                continue
            for value in values:
                entry_lines.append(f"  {predicate} {format_value(label, value)} ;")
        if is_data and not wrote_access_level:
            entry_lines.append(f"  sagegov:accessLevel sagegov:AnonymousOrOpen ;")
        entry_lines.append(f"  dct:source {literal(SOURCE_NOTE)} .")
        lines.append("\n".join(entry_lines))
    return "\n\n".join(lines).strip() + "\n"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT, help="Path to the governance Excel file")
    parser.add_argument("--sheet", default="Table", help="Worksheet name to parse")
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT, help="Destination Turtle file")
    args = parser.parse_args(argv)

    if not args.input.exists():
        parser.error(f"Input file {args.input} not found")

    df = pd.read_excel(args.input, sheet_name=args.sheet, header=None)
    profiles = collect_profiles(df)
    if not profiles:
        parser.error("No profiles found in the worksheet")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    turtle = build_turtle(profiles)
    args.output.write_text(turtle, encoding="utf-8")
    print(f"Wrote {args.output.relative_to(pathlib.Path.cwd()) if args.output.is_absolute() else args.output} ({len(profiles)} profiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
