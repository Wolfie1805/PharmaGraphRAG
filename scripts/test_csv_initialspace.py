import csv
import io

raw = '"Faustan", "Faustan,", "Freudal"'
print("Default csv.reader:", list(csv.reader(io.StringIO(raw))))
print("skipinitialspace=True:", list(csv.reader(io.StringIO(raw), skipinitialspace=True)))
