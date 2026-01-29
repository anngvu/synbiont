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
    ("Redistribution", "sagegov:redistributable"),
    ("Affiliation Requirement", "sagegov:accessPrerequisite"),
    ("Synapse Account", "sagegov:requireSynapseAccount"),
    ("Human Subjects Training", "sagegov:requireHumanSubjectsTraining"),
    ("Data Access Request", "sagegov:requireDataAccessRequest"),
    ("Data Use Certificate Signed by Signing Official", "sagegov:requireDataUseCertificate"),
    ("General description of research objectives (posted)", "sagegov:requireResearchObjective"),
    ("Proof of IRB approval", "sagegov:requireIrbApproval"),
    ("Technical environment security standards", "sagegov:requireSecurity"),
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
EXCEPTION_MARKER = "**"
ACCESS_LEVEL_DEFS = {
    "AnonymousOrOpen": {
        "label": "Anonymous / Open",
        "comment": "Data is usable without registration or affiliation.",
    },
    "Registered": {
        "label": "Registered",
        "comment": "Data usage requires a Synapse account but not additional governance approvals.",
    },
    "RestrictedOrLimited": {
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
SECURITY_STANDARD_DEFS = {
    "NoSecurityStandard": {
        "label": "No security standard required",
        "comment": "No specific technical environment requirements declared.",
    },
    "NIST800171": {
        "label": "NIST 800-171",
        "comment": "Environment aligned with NIST Special Publication 800-171.",
    },
    "ISO27001": {
        "label": "ISO 27001",
        "comment": "Environment aligned with the ISO/IEC 27001 information security standard.",
    },
    "SecureCompliantEnclave": {
        "label": "Secure compliant enclave",
        "comment": "Data must remain inside a secured enclave that satisfies contributor requirements.",
    },
}
SECURITY_STANDARD_KEYWORDS = {
    "NoSecurityStandard": [["no"]],
    "NIST800171": [["nist", "800", "171"]],
    "ISO27001": [["iso", "27001"]],
    "SecureCompliantEnclave": [["secure", "enclave"]],
}
PROPERTY_DECLARATIONS = {
    "sagegov:hasCapability": {
        "label": "has capability",
        "comment": "Generic capability fact derived from the governance reference table.",
    },
    "sagegov:hasAccessPrerequisite": {
        "label": "has access prerequisite",
        "comment": "Prerequisite requirement that must be satisfied before access is granted.",
    },
    "sagegov:allowsException": {
        "label": "allows exception",
        "comment": "Marks requirements that support limited contributor exceptions.",
    },
    "sagegov:approvalProcess": {
        "label": "approval process",
        "comment": "Describes how data access requests are reviewed.",
    },
    "sagegov:requireSynapseAccount": {
        "label": "require Synapse account",
        "comment": "Indicates whether requestors must hold an active Synapse account.",
    },
    "sagegov:recommendedAccessLevel": {
        "label": "recommended access level",
        "comment": "Heuristic access tier recommended by governance reasoning.",
    },
}
SUBPROPERTY_MAP = {
    "sagegov:humanSubjectsTraining": "sagegov:hasAccessPrerequisite",
    "sagegov:dataAccessRequest": "sagegov:hasAccessPrerequisite",
    "sagegov:dataUseCertificate": "sagegov:hasAccessPrerequisite",
    "sagegov:researchObjectiveRequirement": "sagegov:hasAccessPrerequisite",
    "sagegov:irbApproval": "sagegov:hasAccessPrerequisite",
    "sagegov:securityRequirements": "sagegov:hasAccessPrerequisite",
}
MANUAL_SUBPROPERTY_ASSERTIONS = {
    "sagegov:requireSynapseAccount": "sagegov:hasAccessPrerequisite",
}
RESERVED_IDENTIFIERS = set(ACCESS_LEVEL_DEFS.keys()) | set(IDENTIFIABILITY_RISK_DEFS.keys()) | set(SECURITY_STANDARD_DEFS.keys())
SOURCE_NOTE = "reference/DataTypes-brief-Sept2025.xlsx"
PREFIX_BLOCK = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix sagegov: <https://synapse.org/synbiont/governance/> .
"""
CLASS_BLOCK = """
sagegov:AccessProfile rdf:type owl:Class ;
  rdfs:label "Sage governance access profile" ;
  rdfs:comment "Profiles derived from the Sage governance reference spreadsheet." .

sagegov:Data rdf:type owl:Class ;
  rdfs:label "Sage data type" ;
  rdfs:comment "Data classifications referenced in governance policies." ;
  rdfs:subClassOf <http://purl.obolibrary.org/obo/IAO_0000027> .

sagegov:AccessLevel rdf:type owl:Class ;
  rdfs:label "Access level" ;
  rdfs:comment "Permitted usage tiers for Synapse data." .

sagegov:SecurityStandard rdf:type owl:Class ;
  rdfs:label "Security standard" ;
  rdfs:comment "Required technical environment controls for handling data." .

sagegov:AccessProcess
  rdfs:label "Access process" ;
  rdfs:comment "Named procedures used to approve or deny data access." .

sagegov:DataAccessCommitteeApproval rdfs:subClassOf sagegov:AccessProcess ;
  rdfs:label "Data Access Committee approval" ;
  rdfs:comment "Approval performed manually by the Sage Data Access Committee." .

sagegov:SynapseAccountCheck rdfs:subClassOf sagegov:AccessProcess ;
  rdfs:label "Synapse account check" ;
  rdfs:comment "Approval step that only validates the requester has an active Synapse account." .

sagegov:AutomatedClickwrap rdfs:subClassOf sagegov:AccessProcess ;
  rdfs:label "Automated clickwrap" ;
  rdfs:comment "Automatic approval that relies on a click-through agreement." .

sagegov:IdentifiabilityRisk rdf:type owl:Class ;
  rdfs:label "Identifiability risk" ;
  rdfs:comment "Relative likelihood that data could be used to re-identify individuals." .

sagegov:AccessProfileRule rdf:type owl:Class ;
  rdfs:label "Governance rule" ;
  rdfs:comment "Helper class for constraints referenced inside the governance module." ;
  rdfs:isDefinedBy sagegov:AccessProfile ."""


def camel_case_identifier(value: str, seen: Dict[str, int]) -> str:
    safe_value = value.replace("/", " Or ")
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", safe_value.strip()) if p]
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
    blocks: List[str] = []
    for term, meta in ACCESS_LEVEL_DEFS.items():
        lines = [
            f"sagegov:{term}",
            f"  rdfs:subClassOf sagegov:AccessLevel ;",
            f"  skos:prefLabel {literal(meta['label'])} ;",
        ]
        if meta.get("comment"):
            lines.append(f"  rdfs:comment {literal(meta['comment'])} ;")
        lines[-1] = lines[-1].rstrip(" ;") + " ."
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def identifiability_risk_term(value: str) -> Optional[str]:
    normalized = re.sub(r"[^a-z0-9]+", "", normalize_text(value).lower())
    return IDENTIFIABILITY_RISK_LOOKUP.get(normalized)


def identifiability_risk_defs_block() -> str:
    blocks: List[str] = []
    for term, meta in IDENTIFIABILITY_RISK_DEFS.items():
        lines = [
            f"sagegov:{term}",
            f"  rdfs:subClassOf sagegov:IdentifiabilityRisk ;",
            f"  skos:prefLabel {literal(meta['label'])} ;",
        ]
        if meta.get("comment"):
            lines.append(f"  rdfs:comment {literal(meta['comment'])} ;")
        lines[-1] = lines[-1].rstrip(" ;") + " ."
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def security_standard_terms(value: str) -> List[str]:
    text = normalize_text(value).lower().replace("/", " ")
    matches: List[str] = []
    for term, patterns in SECURITY_STANDARD_KEYWORDS.items():
        for tokens in patterns:
            if all(token in text for token in tokens):
                matches.append(term)
                break
    return matches


def security_standard_defs_block() -> str:
    blocks: List[str] = []
    for term, meta in SECURITY_STANDARD_DEFS.items():
        lines = [
            f"sagegov:{term} rdf:type sagegov:SecurityStandard ;",
            f"  skos:prefLabel {literal(meta['label'])} ;",
        ]
        if meta.get("comment"):
            lines.append(f"  rdfs:comment {literal(meta['comment'])} ;")
        lines[-1] = lines[-1].rstrip(" ;") + " ."
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def property_axioms_block() -> str:
    blocks: List[str] = []
    for iri, meta in PROPERTY_DECLARATIONS.items():
        lines = [
            f"{iri} rdf:type rdf:Property ;",
            f"  rdfs:label {literal(meta['label'])} ;",
        ]
        comment = meta.get("comment")
        if comment:
            lines.append(f"  rdfs:comment {literal(comment)} ;")
        lines[-1] = lines[-1].rstrip(" ;") + " ."
        blocks.append("\n".join(lines))
    for child, parent in SUBPROPERTY_MAP.items():
        local_name = child.split(":", 1)[1]
        require_child = f"sagegov:require{local_name[0].upper()}{local_name[1:]}"
        lines = [
            f"{require_child} rdf:type rdf:Property ;",
            f"  rdfs:subPropertyOf {parent} ;",
            f"  owl:equivalentProperty {child} .",
        ]
        blocks.append("\n".join(lines))
    for child, parent in MANUAL_SUBPROPERTY_ASSERTIONS.items():
        blocks.append(f"{child} rdfs:subPropertyOf {parent} .")
    return "\n\n".join(blocks)


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
        security_standard_defs_block().strip(),
        property_axioms_block().strip(),
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
        classes: List[str] = []
        access_profile_flag = not is_data
        label_norm = normalize_label_text(pref_label).lower()
        if label_norm in ALSO_DATA_LABELS:
            is_data = True
            access_profile_flag = False
        if access_profile_flag:
            classes.append("sagegov:AccessProfile")
        entry_lines = []
        if classes:
            entry_lines.append(f"sagegov:{node_id} rdf:type {', '.join(classes)} ;")
        else:
            entry_lines.append(f"sagegov:{node_id}")
        entry_lines.append(f"  skos:prefLabel {literal(pref_label)} ;")
        for alt in alt_labels:
            entry_lines.append(f"  skos:altLabel {literal(alt)} ;")
        if is_data:
            entry_lines.append("  rdfs:subClassOf sagegov:Data ;")
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
            if label == "Technical environment security standards":
                for value in values:
                    terms = security_standard_terms(value)
                    if terms:
                        for term in terms:
                            entry_lines.append(f"  {predicate} sagegov:{term} ;")
                    else:
                        entry_lines.append(f"  {predicate} {literal(value)} ;")
                continue
            if label == "Approval Process":
                for value in values:
                    normalized = normalize_text(value)
                    lowered = normalized.lower()
                    if lowered == "no":
                        continue
                    if "dac" in lowered:
                        entry_lines.append(f"  {predicate} sagegov:DataAccessCommittee ;")
                        continue
                    if "automated" in lowered and "clickwrap" in lowered:
                        entry_lines.append(f"  {predicate} sagegov:AutomatedClickwrap ;")
                        continue
                    if "synapse" in lowered and "account" in lowered:
                        entry_lines.append(f"  {predicate} sagegov:SynapseAccountCheck ;")
                        continue
                    entry_lines.append(f"  {predicate} {literal(normalized)} ;")
                continue
            for value in values:
                exception_flag = value.endswith(EXCEPTION_MARKER)
                entry_lines.append(f"  {predicate} {format_value(label, value)} ;")
                if exception_flag:
                    entry_lines.append("  sagegov:allowsException true ;")
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
