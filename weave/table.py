class Table:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)
