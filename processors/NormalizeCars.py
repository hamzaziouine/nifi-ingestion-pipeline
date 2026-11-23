"""NormalizeCars: a NiFi 2 Python processor for the HTTP entry point.

HTTP clients post cars in the raw Auto MPG shape (lower-case names, origin as a
numeric code, integers written as floats). The ingestion group expects the CSV
layout its record readers use, and it derives the `source` attribute from the
part of the file name before the first underscore. This processor bridges the two:

    [{"car name": "toyota corolla", "mpg": 29.0, "horsepower": 75.0, "origin": 3, ...}]
    ->
    Car,MPG,Cylinders,Displacement,Horsepower,Weight,Acceleration,Model,Origin
    Toyota Corolla,29,4,97,75,2171,16,75,Japan

    filename = web_20261028_175415_123.csv

It does not validate values. Anything it cannot convert is passed through as text
(or left empty) so that ValidateRecord rejects the row with a precise reason and the
rest of the payload still gets loaded.

The pure functions at the top are what the unit tests exercise; the NiFi class at the
bottom only wires them to the FlowFile API.
"""

import csv
import io
import json
import re
from datetime import datetime, timezone

from nifiapi.flowfiletransform import FlowFileTransform, FlowFileTransformResult
from nifiapi.properties import PropertyDescriptor, StandardValidators

COLUMNS = ["Car", "MPG", "Cylinders", "Displacement", "Horsepower",
           "Weight", "Acceleration", "Model", "Origin"]

# output column -> key in the raw payload (UCI attribute names)
RAW_KEYS = {
    "MPG": "mpg",
    "Cylinders": "cylinders",
    "Displacement": "displacement",
    "Horsepower": "horsepower",
    "Weight": "weight",
    "Acceleration": "acceleration",
    "Model": "model year",
}

DEFAULT_ORIGINS = "1=US,2=Europe,3=Japan"
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9-]+$")
MISSING = {"", "?", "na", "n/a", "null", "none"}


def parse_origin_mapping(text):
    """'1=US, 2=Europe' -> {'1': 'US', '2': 'Europe'}. Raises ValueError if malformed."""
    mapping = {}
    for pair in text.split(","):
        if not pair.strip():
            continue
        code, sep, label = pair.partition("=")
        if not sep or not code.strip() or not label.strip():
            raise ValueError(f"invalid origin mapping entry: {pair.strip()!r}")
        mapping[code.strip()] = label.strip()
    if not mapping:
        raise ValueError("origin mapping is empty")
    return mapping


def format_number(value):
    """Render a raw numeric value the way the CSV schema expects it.

    Missing values become an empty cell (null). Whole numbers lose their '.0' so that
    int columns validate (75.0 -> '75'). Other floats keep their decimals. Text that is
    not a number is returned stripped, so schema validation can flag it.
    """
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if text.lower() in MISSING:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if number != number or number in (float("inf"), float("-inf")):
        return ""
    if number.is_integer():
        return str(int(number))
    return repr(number)


def title_case(name):
    """'chevrolet chevelle malibu' -> 'Chevrolet Chevelle Malibu' (whitespace collapsed)."""
    return " ".join(word.capitalize() for word in str(name or "").split())


def normalize_record(raw, origins):
    """One raw car dict -> list of CSV cells in COLUMNS order."""
    row = [title_case(raw.get("car name"))]
    for column in COLUMNS[1:-1]:
        row.append(format_number(raw.get(RAW_KEYS[column])))
    code = format_number(raw.get("origin"))
    row.append(origins.get(code, ""))  # unknown code -> empty -> rejected downstream
    return row


def to_csv(records, origins):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for raw in records:
        writer.writerow(normalize_record(raw, origins))
    return out.getvalue()


def load_records(content):
    """Parse the request body. Accepts a JSON array of objects or a single object."""
    data = json.loads(content)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        raise ValueError("expected a non-empty JSON array of objects")
    if not all(isinstance(item, dict) for item in data):
        raise ValueError("every array item must be a JSON object")
    return data


def build_filename(prefix, now):
    """<prefix>_<UTC yyyyMMdd_HHmmss_mmm>.csv; the prefix becomes the `source` attribute."""
    return f"{prefix}_{now:%Y%m%d_%H%M%S}_{now.microsecond // 1000:03d}.csv"


class NormalizeCars(FlowFileTransform):

    class Java:
        implements = ["org.apache.nifi.python.processor.FlowFileTransform"]

    class ProcessorDetails:
        version = "1.0.0"
        description = ("Converts a JSON array of cars in the raw Auto MPG shape into the CSV "
                       "layout read by the ingestion flow, and names the file "
                       "<prefix>_<UTC timestamp>.csv so the prefix becomes the source attribute.")
        tags = ["json", "csv", "normalization", "auto-mpg"]

    ORIGIN_MAPPING = PropertyDescriptor(
        name="Origin Mapping",
        description="Origin codes and labels as code=label pairs separated by commas.",
        required=True,
        default_value=DEFAULT_ORIGINS,
        validators=[StandardValidators.NON_EMPTY_VALIDATOR])

    SOURCE_PREFIX = PropertyDescriptor(
        name="Source Prefix",
        description=("File name prefix. Letters, digits and '-' only: the ingestion group "
                     "reads everything before the first '_' as the source."),
        required=True,
        default_value="web",
        validators=[StandardValidators.NON_EMPTY_VALIDATOR])

    def __init__(self, **kwargs):
        super().__init__()

    def getPropertyDescriptors(self):
        return [self.ORIGIN_MAPPING, self.SOURCE_PREFIX]

    def transform(self, context, flowfile):
        prefix = context.getProperty(self.SOURCE_PREFIX).getValue().strip()
        if not PREFIX_PATTERN.match(prefix):
            self.logger.error(f"Source Prefix {prefix!r} must match {PREFIX_PATTERN.pattern}")
            return FlowFileTransformResult(relationship="failure")

        try:
            origins = parse_origin_mapping(context.getProperty(self.ORIGIN_MAPPING).getValue())
            records = load_records(flowfile.getContentsAsBytes())
        except ValueError as error:
            self.logger.error(f"Cannot normalize payload: {error}")
            return FlowFileTransformResult(relationship="failure")

        return FlowFileTransformResult(
            relationship="success",
            contents=to_csv(records, origins),
            attributes={
                "filename": build_filename(prefix, datetime.now(timezone.utc)),
                "mime.type": "text/csv",
                "cars.received": str(len(records)),
            })
