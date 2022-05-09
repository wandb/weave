import csv


def load_csv(path):
    with open(path) as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024), delimiters=";,")
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


def save_csv(path, csv_data):
    if not csv_data:
        field_names = []
    else:
        field_names = list(csv_data[0].keys())
    with open(path, "w") as f:
        writer = csv.DictWriter(f, field_names, delimiter=";")
        writer.writeheader()
        for row in csv_data:
            writer.writerow(row)
