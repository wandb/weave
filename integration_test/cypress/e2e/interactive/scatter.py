import random

import weave
from weave.legacy.ecosystem import wandb
from weave.show import show_url

weave.use_fixed_server_port()

data = weave.save(
    [
        {
            "a": random.gauss(5, 2),
            "b": random.gauss(0, 9),
            "c": random.gauss(15, 0.9),
            "d": random.random(),
            "e": random.choice(["a", "b"]),
        }
        for i in range(500)
    ]
)

panel: weave.legacy.panels.Group = weave.legacy.panels.Group(
    items={
        "scatter": wandb.Scatter(  # type: ignore
            data, x_fn=lambda item: item["a"], y_fn=lambda item: item["b"]
        ),
        "table": lambda scatter: weave.legacy.panels.LabeledItem(
            label="Selected items",
            item=weave.legacy.panels.Group(
                style="height: 400px;",
                preferHorizontal=True,
                items={"table": scatter.selected()},
            ),
        ),
    }
)

print(show_url(panel))
