import csv
import json

import pytest

from helpers import execute


@pytest.fixture()
def schema_file(tmp_path):
    p = tmp_path / "schema.json"
    schema = {
        "fields": [{"name": "field-1"}],
        "digital-land": {"fields": ["field-1"]},
    }
    with open(p, "w") as f:
        json.dump(schema, f)
    return p


@pytest.fixture()
def input_file_csv(tmp_path):
    p = tmp_path / "input.csv"
    fieldnames = ["field-1", "field-2", "field-3"]
    with open(p, "w") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "field-1": "row-1-data-1",
                "field-2": "row-1-data-2",
                "field-3": "row-1-data-3",
            }
        )
        writer.writerow(
            {
                "field-1": "row-2-data-1",
                "field-2": "row-2-data-2",
                "field-3": "row-2-data-3",
            }
        )
    return p


@pytest.mark.skip(reason="rearchiecture underway, fix later TODO")
def test_harmonise_identity(schema_file, input_file_csv):
    output_file = input_file_csv.with_suffix(".out")
    returncode, outs, errs = execute(
        ["digital-land", "harmonise", input_file_csv, output_file, schema_file]
    )

    assert returncode == 0, f"return code non-zero, output:\n{errs}"
    assert "ERROR" not in errs

    output = read_csv(output_file)
    assert len(output) == 2
    # __import__("pdb").set_trace()


# def _test_convert(input_file):
#     output_file = input_file.with_suffix(".out")
#     print(f"output  file: {output_file}")
#     returncode, outs, errs = execute(
#         ["digital-land", "convert", input_file, output_file]
#     )

#     assert returncode == 0, "return code non-zero"
#     assert "ERROR" not in errs

#     output = read_csv(output_file)
#     assert len(output) == 2
#     assert output[0]["field-1"] == "row-1-data-1"
#     assert output[1]["field-3"] == "row-2-data-3"


def read_csv(file):
    with open(file) as f:
        csv_reader = csv.DictReader(f)
        return list(csv_reader)
