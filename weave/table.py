import typing


class Table:
    def __init__(self, rows: typing.List) -> None:
        self.rows = rows

    def __iter__(self) -> typing.Iterator:
        return iter(self.rows)
