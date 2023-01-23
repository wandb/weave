import csv
from .. import api as weave
from .. import file_base


def load_csv(csvfile):
    dialect = csv.Sniffer().sniff(csvfile.read(10240), delimiters=";,")
    csvfile.seek(0)
    reader = csv.reader(csvfile, dialect)
    header = next(reader)
    col_types = {}
    for key in header:
        col_types[key] = int

    # shitty type guessing
    rows = []
    for raw_row in reader:
        rows.append(raw_row)
        for key, val in zip(header, raw_row):
            cur_col_type = col_types[key]
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                    if cur_col_type == int:
                        col_types[key] = float
                except ValueError:
                    if cur_col_type != str:
                        col_types[key] = str
    final_rows = []
    for raw_row in rows:
        row = {}
        for key, val in zip(header, raw_row):
            row[key] = col_types[key](val)
        final_rows.append(row)
    return final_rows


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
