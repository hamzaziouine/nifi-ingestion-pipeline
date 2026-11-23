"""Checks that the versioned flow, the reference schema, the DDL and the Python
processor agree with each other, and that no secret ever lands in the flow file."""

import json
import re
from pathlib import Path

import pytest

import NormalizeCars as nc

ROOT = Path(__file__).resolve().parents[1]
FLOW = json.loads((ROOT / "flows" / "ingestion-cars.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "cars.avsc").read_text(encoding="utf-8"))
DDL = (ROOT / "infra" / "mysql" / "01_cars.sql").read_text(encoding="utf-8")

GROUP = FLOW["flowContents"]


def service(name):
    return next(s for s in GROUP["controllerServices"] if s["name"] == name)


def fields(schema):
    """[(name, normalised type)], ignoring names/namespaces of nested types."""
    out = []
    for field in schema["fields"]:
        kind = field["type"]
        if isinstance(kind, dict):
            kind = (kind["type"], tuple(kind.get("symbols", ())))
        elif isinstance(kind, list):
            kind = tuple(kind)
        out.append((field["name"], kind))
    return out


def test_reference_schema_matches_the_one_embedded_in_the_flow():
    embedded = json.loads(service("CSVReader cars")["properties"]["Schema Text"])
    assert fields(SCHEMA) == fields(embedded)


def test_query_reader_only_relaxes_origin():
    strict = fields(json.loads(service("CSVReader cars")["properties"]["Schema Text"]))
    relaxed = fields(json.loads(service("CSVReader requêtes")["properties"]["Schema Text"]))
    assert strict[:-1] == relaxed[:-1]
    assert relaxed[-1] == ("Origin", "string")


def test_processor_writes_the_schema_columns_in_order():
    assert nc.COLUMNS == [f["name"] for f in SCHEMA["fields"]]


def test_table_has_exactly_the_record_columns():
    body = DDL[DDL.index("(") + 1:DDL.rindex(")")]
    columns = [m.group(1) for m in re.finditer(r"^\s{2}([A-Z][A-Za-z]+)\s+[A-Z]", body, re.M)]
    assert columns == nc.COLUMNS


def test_origin_values_agree_everywhere():
    enum = SCHEMA["fields"][-1]["type"]["symbols"]
    assert sorted(nc.parse_origin_mapping(nc.DEFAULT_ORIGINS).values()) == sorted(enum)
    check = re.search(r"Origin IN \(([^)]*)\)", DDL).group(1)
    assert sorted(re.findall(r"'([^']+)'", check)) == sorted(enum)


def parameters():
    (context,) = FLOW["parameterContexts"].values()
    return {p["name"]: p for p in context["parameters"]}


def test_sensitive_parameters_have_no_committed_value():
    sensitive = {name: p for name, p in parameters().items() if p["sensitive"]}
    assert set(sensitive) == {"cle_acces_minio", "cle_secrete_minio", "mot_de_passe_mysql"}
    assert all(p.get("value") is None for p in sensitive.values())


@pytest.mark.parametrize("prop", ["Password", "Secret Access Key", "Access Key ID"])
def test_secret_properties_only_reference_parameters(prop):
    found = [s["properties"][prop] for s in GROUP["controllerServices"] if prop in s["properties"]]
    assert found, prop
    assert all(re.fullmatch(r"#\{[a-z_]+\}", value) for value in found)


def test_flow_file_has_no_token_like_strings():
    text = (ROOT / "flows" / "ingestion-cars.json").read_text(encoding="utf-8")
    assert not re.search(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_|AKIA[0-9A-Z]{16}|PRIVATE KEY", text)
