import csv
from .. import api as weave
from .. import file_base


def convert_type(val):
    if val is None:
        return val
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return val


def load_csv(csvfile):
    dialect = csv.Sniffer().sniff(csvfile.read(10240), delimiters=";,")
    csvfile.seek(0)
    reader = csv.DictReader(csvfile, dialect=dialect)
    rows = []
    for row in reader:
        print("ROW", row)
        # DictReader puts items that don't have a header into a list under
        # the None key. This happens for mal-formed csvs. Ignore the None
        # key.
        rows.append({k: convert_type(v) for k, v in row.items() if k is not None})
    return rows


def save_csv(csvfile, csv_data):
    if not csv_data:
        field_names = []
    else:
        field_names = list(csv_data[0].keys())
    writer = csv.DictWriter(csvfile, field_names, delimiter=";")
    writer.writeheader()
    for row in csv_data:
        writer.writerow(row)


def writecsv(self: file_base.File, csv_data: list[dict]):
    with self.open("w") as f:
        save_csv(f, csv_data)


@weave.op(
    name="file-refine_readcsv",
    input_type={"self": file_base.FileBaseType(extension=weave.types.literal("csv"))},
)
def refine_readcsv(self) -> weave.types.Type:
    with self.open() as f:
        return weave.types.TypeRegistry.type_of(load_csv(f))


@weave.op(
    # TODO: I had to mark pure=False
    # But that's not true! We need to know if the file we're reading is
    # immutable (inside an artifact) or not (on a filesystem).
    setter=writecsv,
    name="file-readcsv",
    input_type={"self": file_base.FileBaseType(extension=weave.types.literal("csv"))},
    output_type=weave.types.List(weave.types.TypedDict({})),
    refine_output_type=refine_readcsv,
)
def readcsv(self):
    with self.open() as f:
        return load_csv(f)
