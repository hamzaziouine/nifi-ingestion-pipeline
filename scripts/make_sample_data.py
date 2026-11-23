"""Build the sample files in data/sample/ from the UCI Auto MPG dataset.

    python scripts/make_sample_data.py                     # downloads auto-mpg.data
    python scripts/make_sample_data.py --source auto-mpg.data

Outputs:
    cars_full.csv       all 398 cars in the CSV layout the flow validates
    cars_malformed.csv  20 good rows plus 5 broken ones, to exercise the quarantine
    web_cars.json       10 cars in the raw shape, for the HTTP entry point
                        (the last one has an unknown origin code on purpose)

Dataset: Quinlan, R. (1993). Auto MPG. UCI Machine Learning Repository,
https://doi.org/10.24432/C5859H, licensed CC BY 4.0.
"""

import argparse
import csv
import json
import shlex
import urllib.request
from pathlib import Path

URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/auto-mpg/auto-mpg.data"
COLUMNS = ["Car", "MPG", "Cylinders", "Displacement", "Horsepower",
           "Weight", "Acceleration", "Model", "Origin"]
ORIGINS = {"1": "US", "2": "Europe", "3": "Japan"}
RAW_FIELDS = ["mpg", "cylinders", "displacement", "horsepower",
              "weight", "acceleration", "model year", "origin"]


def parse_line(line):
    """One auto-mpg.data line -> raw dict with UCI attribute names (values as in the file)."""
    numbers, _, name = line.partition("\t")
    values = numbers.split()
    if len(values) != len(RAW_FIELDS):
        raise ValueError(f"expected {len(RAW_FIELDS)} numeric fields: {line!r}")
    raw = dict(zip(RAW_FIELDS, values))
    raw["car name"] = shlex.split(name)[0]
    return raw


def to_row(raw):
    """Raw dict -> CSV row matching the flow schema."""
    def num(text, integer=False):
        value = float(text)
        return str(int(value)) if integer else str(value)

    return [
        " ".join(word.capitalize() for word in raw["car name"].split()),
        num(raw["mpg"]),
        num(raw["cylinders"], integer=True),
        num(raw["displacement"]),
        "" if raw["horsepower"] == "?" else num(raw["horsepower"], integer=True),
        num(raw["weight"], integer=True),
        num(raw["acceleration"]),
        num(raw["model year"], integer=True),
        ORIGINS[raw["origin"]],
    ]


def to_web(raw):
    """Raw dict -> JSON object as an upstream API would send it (numbers as floats)."""
    obj = {key: (None if raw[key] == "?" else float(raw[key])) for key in RAW_FIELDS}
    obj["origin"] = int(raw["origin"])
    obj["car name"] = raw["car name"]
    return obj


# Each broken row breaks one rule of the schema.
BROKEN = [
    ["Plymouth Duster", "22.0", "6", "198.0", "ninety-five", "2833", "15.5", "70", "US"],  # text in an int
    ["Saab 99e", "25.0", "4", "104.0", "95", "2375", "17.5", "70", "Sweden"],              # not in the enum
    ["Honda Civic", "", "4", "91.0", "53", "1795", "17.5", "75", "Japan"],                 # MPG is required
    ["Fiat 128", "29.0", "4", "68.0", "49", "1867", "19.5", "73"],                         # Origin missing
    ["Ford Pinto", "25.0", "4", "98.0", "", "2046", "19.0", "71", ""],                     # empty enum value
]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", type=Path, help="local auto-mpg.data (downloaded if omitted)")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "sample")
    args = parser.parse_args()

    if args.source:
        text = args.source.read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            text = response.read().decode("utf-8")

    raws = [parse_line(line) for line in text.splitlines() if line.strip()]
    rows = [to_row(raw) for raw in raws]
    args.out.mkdir(parents=True, exist_ok=True)

    write_csv(args.out / "cars_full.csv", rows)
    write_csv(args.out / "cars_malformed.csv", rows[:20] + BROKEN)

    web = [to_web(raw) for raw in raws[::40][:9]]
    web.append(dict(to_web(raws[-1]), origin=4))
    (args.out / "web_cars.json").write_text(json.dumps(web, indent=2) + "\n", encoding="utf-8")

    missing_hp = sum(1 for row in rows if row[4] == "")
    japan = sum(1 for row in rows if row[8] == "Japan")
    print(f"cars_full.csv: {len(rows)} rows ({missing_hp} without horsepower, {japan} from Japan)")
    print(f"cars_malformed.csv: 20 valid + {len(BROKEN)} broken rows")
    print(f"web_cars.json: {len(web)} objects")


if __name__ == "__main__":
    main()
