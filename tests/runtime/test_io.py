import csv

from scrapewizard_runtime.io import write_csv


def test_write_csv_handles_records_with_different_fields(tmp_path):
    path = tmp_path / "data.csv"
    write_csv([{"title": "A"}, {"title": "B", "price": "9"}], path)

    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert rows == [{"title": "A", "price": ""}, {"title": "B", "price": "9"}]
