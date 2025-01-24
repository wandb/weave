# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weave @ ..",
# ]
# ///

from __future__ import annotations

import pydantic

import weave

weave.init("mem-test-3")


class Human(pydantic.BaseModel):
    parent: Human | None = pydantic.Field(default=None)
    children: list[Human] = pydantic.Field(default_factory=list)

    def birth(self) -> Human:
        child = Human(parent=self)
        self.children.append(child)
        return child


@weave.op
def create_human(children: int) -> Human:
    parent = Human()
    for _ in range(children):
        parent.birth()
    return parent

def main() -> None:
    create_human(1)


if __name__ == "__main__":
    main()
