"""The sample files behave the way the docs say: cars_full.csv is fully valid, the malformed
file has exactly five rejects, and the web payload yields nine good rows and one reject."""

import csv
import io
import json
from pathlib import Path

import pytest

import NormalizeCars as nc
import make_sample_data as msd

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
SCHEMA = json.loads((ROOT / "schemas" / "cars.avsc").read_text(encoding="utf-8"))


def is_valid(row):
    """Rough stand-in for ValidateRecord with strict type checking against cars.avsc."""
    if set(row) != {f["name"] for f in SCHEMA["fields"]} or None in row.values():
        return False
    for field in SCHEMA["fields"]:
        value, kind = row[field["name"]], field["type"]
        if isinstance(kind, list):
            if value == "":
                continue
            kind = kind[1]
        if isinstance(kind, dict):
            if value not in kind["symbols"]:
                return False
        elif kind == "string":
            if not value:
                return False
        elif kind == "int":
            try:
                int(value)
            except ValueError:
                return False
        elif kind == "double":
            try:
                float(value)
            except ValueError:
                return False
    return True


def read(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_full_file_is_complete_and_valid():
    rows = read((SAMPLE / "cars_full.csv").read_text(encoding="utf-8"))
    assert len(rows) == 398
    assert all(is_valid(r) for r in rows)
    assert sum(r["Origin"] == "Japan" for r in rows) == 79
    assert sum(r["Horsepower"] == "" for r in rows) == 6


def test_malformed_file_has_five_rejects():
    rows = read((SAMPLE / "cars_malformed.csv").read_text(encoding="utf-8"))
    assert [is_valid(r) for r in rows].count(False) == len(msd.BROKEN) == 5
    assert len(rows) == 25


def test_web_payload_normalizes_to_nine_good_rows():
    payload = (SAMPLE / "web_cars.json").read_bytes()
    origins = nc.parse_origin_mapping(nc.DEFAULT_ORIGINS)
    rows = read(nc.to_csv(nc.load_records(payload), origins))
    assert len(rows) == 10
    assert [is_valid(r) for r in rows] == [True] * 9 + [False]


def test_parse_line_handles_missing_horsepower():
    line = '25.0   4   98.00      ?      2046.      19.0   71  1\t"ford pinto"'
    raw = msd.parse_line(line)
    assert raw["car name"] == "ford pinto"
    assert msd.to_row(raw)[4] == ""
    assert msd.to_web(raw)["horsepower"] is None


def test_parse_line_rejects_short_lines():
    with pytest.raises(ValueError):
        msd.parse_line('25.0 4 98.0\t"x"')
