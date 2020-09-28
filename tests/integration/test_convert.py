import csv

import pytest
import xlsxwriter

from helpers import execute


@pytest.fixture()
def input_file_xlsx(tmp_path):
    path = tmp_path / "input.xlsx"
    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet()
    worksheet.write("A1", "field-1")
    worksheet.write("B1", "field-2")
    worksheet.write("C1", "field-3")
    worksheet.write("A2", "row-1-data-1")
    worksheet.write("B2", "row-1-data-2")
    worksheet.write("C2", "row-1-data-3")
    worksheet.write("A3", "row-2-data-1")
    worksheet.write("B3", "row-2-data-2")
    worksheet.write("C3", "row-2-data-3")
    workbook.close()
    return path


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


@pytest.fixture()
def input_file_geo_json(tmp_path):
    pass


@pytest.fixture()
def input_file_geo_zip(tmp_path):
    pass


def test_convert_xlsx(input_file_xlsx):
    _test_convert(input_file_xlsx)


def test_convert_csv(input_file_csv):
    _test_convert(input_file_csv)


@pytest.mark.skip()
def test_convert_geo_json(input_file_geo_json):
    assert False, "TODO: Implement me"


@pytest.mark.skip()
def test_convert_geo_zip(input_file_geo_zip):
    assert False, "TODO: Implement me"


def _test_convert(input_file):
    output_file = input_file.with_suffix(".out")
    print(f"output  file: {output_file}")
    returncode, outs, errs = execute(
        [
            "digital-land",
            "convert",
            "some-pipeline",
            input_file,
            output_file,
            "tests/data/pipeline",
        ]
    )

    assert returncode == 0, f"return code non-zero: {errs}"
    assert "ERROR" not in errs

    output = read_csv(output_file)
    assert len(output) == 2
    assert output[0]["field-1"] == "row-1-data-1"
    assert output[1]["field-3"] == "row-2-data-3"


def read_csv(file):
    with open(file) as f:
        csv_reader = csv.DictReader(f)
        return list(csv_reader)
