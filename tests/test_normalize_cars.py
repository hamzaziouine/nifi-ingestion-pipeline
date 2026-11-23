import csv
import io
import json
import re
from datetime import datetime, timezone

import pytest

import NormalizeCars as nc

ORIGINS = nc.parse_origin_mapping(nc.DEFAULT_ORIGINS)

RAW_COROLLA = {
    "mpg": 29.0, "cylinders": 4, "displacement": 97.0, "horsepower": 75.0,
    "weight": 2171.0, "acceleration": 16.0, "model year": 75, "origin": 3,
    "car name": "toyota  corolla",
}


def rows(csv_text):
    return list(csv.reader(io.StringIO(csv_text)))


class Prop:
    def __init__(self, value):
        self.value = value

    def getValue(self):
        return self.value


class Context:
    def __init__(self, origins=nc.DEFAULT_ORIGINS, prefix="web"):
        self.values = {"Origin Mapping": origins, "Source Prefix": prefix}

    def getProperty(self, descriptor):
        return Prop(self.values[descriptor.name])


class FlowFile:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def getContentsAsBytes(self):
        return self.payload


# --- pure functions ---------------------------------------------------------

def test_origin_mapping_parses_and_trims():
    assert nc.parse_origin_mapping(" 1 = US , 2=Europe,") == {"1": "US", "2": "Europe"}


@pytest.mark.parametrize("text", ["", "1US", "=US", "1=", ","])
def test_origin_mapping_rejects_malformed(text):
    with pytest.raises(ValueError):
        nc.parse_origin_mapping(text)


@pytest.mark.parametrize("raw, expected", [
    (75.0, "75"),          # int column written as float upstream
    ("2130.", "2130"),
    (15.5, "15.5"),
    (0.1, "0.1"),
    (None, ""),
    ("?", ""),             # UCI marks missing horsepower with '?'
    ("n/a", ""),
    (" ", ""),
    (float("nan"), ""),
    (True, ""),
    ("ninety", "ninety"),  # left as text so ValidateRecord rejects the row
])
def test_format_number(raw, expected):
    assert nc.format_number(raw) == expected


def test_title_case_collapses_whitespace():
    assert nc.title_case("  chevrolet   chevelle malibu ") == "Chevrolet Chevelle Malibu"
    assert nc.title_case(None) == ""


def test_normalize_record_maps_every_column():
    assert nc.normalize_record(RAW_COROLLA, ORIGINS) == [
        "Toyota Corolla", "29", "4", "97", "75", "2171", "16", "75", "Japan"]


def test_unknown_origin_code_becomes_empty():
    raw = dict(RAW_COROLLA, origin=4)
    assert nc.normalize_record(raw, ORIGINS)[-1] == ""


def test_csv_has_header_and_one_row_per_car():
    out = rows(nc.to_csv([RAW_COROLLA, dict(RAW_COROLLA, horsepower="?")], ORIGINS))
    assert out[0] == nc.COLUMNS
    assert len(out) == 3
    assert out[2][4] == ""


def test_names_with_commas_are_quoted():
    text = nc.to_csv([dict(RAW_COROLLA, **{"car name": "ford, pinto"})], ORIGINS)
    assert '"Ford, Pinto"' in text
    assert rows(text)[1][0] == "Ford, Pinto"


@pytest.mark.parametrize("payload", [b"[]", b"42", b"[1, 2]", b"not json", b"\xff\xfe"])
def test_load_records_rejects_bad_payloads(payload):
    with pytest.raises(ValueError):
        nc.load_records(payload)


def test_load_records_accepts_single_object():
    assert nc.load_records(json.dumps(RAW_COROLLA).encode()) == [RAW_COROLLA]


def test_filename_prefix_is_the_source():
    now = datetime(2026, 10, 28, 17, 54, 15, 123456, tzinfo=timezone.utc)
    name = nc.build_filename("web", now)
    assert name == "web_20261028_175415_123.csv"
    # the flow derives source with ${filename:substringBefore('_')}
    assert name.split("_", 1)[0] == "web"


# --- processor wiring -------------------------------------------------------

def test_transform_success():
    processor = nc.NormalizeCars()
    result = processor.transform(Context(), FlowFile([RAW_COROLLA, dict(RAW_COROLLA, origin=1)]))
    assert result.relationship == "success"
    assert rows(result.contents)[2][-1] == "US"
    assert result.attributes["cars.received"] == "2"
    assert result.attributes["mime.type"] == "text/csv"
    assert re.fullmatch(r"web_\d{8}_\d{6}_\d{3}\.csv", result.attributes["filename"])


def test_transform_routes_invalid_json_to_failure():
    processor = nc.NormalizeCars()
    result = processor.transform(Context(), FlowFile(b"{oops"))
    assert result.relationship == "failure"
    assert processor.logger.errors


@pytest.mark.parametrize("prefix", ["web_api", "web api", ""])
def test_transform_rejects_prefix_that_breaks_source(prefix):
    result = nc.NormalizeCars().transform(Context(prefix=prefix), FlowFile([RAW_COROLLA]))
    assert result.relationship == "failure"


def test_transform_rejects_bad_origin_mapping():
    result = nc.NormalizeCars().transform(Context(origins="1US"), FlowFile([RAW_COROLLA]))
    assert result.relationship == "failure"


def test_descriptors_exposed():
    names = [d.name for d in nc.NormalizeCars().getPropertyDescriptors()]
    assert names == ["Origin Mapping", "Source Prefix"]
