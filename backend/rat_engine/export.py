"""CSV writing for Contract A exports."""
from __future__ import annotations

import csv

from .metrics import HEADER


def write_csv(rows, out) -> None:
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
