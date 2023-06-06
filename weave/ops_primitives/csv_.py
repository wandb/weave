import csv
import pyarrow as pa
import pyarrow.csv as pa_csv
from .. import api as weave
from .. import file_base


def sniff_dialect(path: str) -> type[csv.Dialect]:
    with open(path, newline="") as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(100 * 1024))
        return dialect


def dialect_to_pyarrow_options(
    dialect: type[csv.Dialect],
) -> tuple[pa_csv.ReadOptions, pa_csv.ParseOptions]:
    # Convert a csv.Dialect object to the corresponding pyarrow options.
    read_options = pa_csv.ReadOptions()
    parse_options = pa_csv.ParseOptions(
        delimiter=dialect.delimiter,
        quote_char=dialect.quotechar,
        double_quote=dialect.doublequote,
        escape_char=dialect.escapechar,
        newlines_in_values=True,
    )
    return read_options, parse_options


def read_csv_with_dialect(path: str) -> pa.Table:
    dialect = sniff_dialect(path)
    read_options, parse_options = dialect_to_pyarrow_options(dialect)
    table = pa_csv.read_csv(
        path, read_options=read_options, parse_options=parse_options
    )
    return table


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
    hidden=True,
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
