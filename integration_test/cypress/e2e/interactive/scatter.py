import random

import weave
from weave.legacy.weave.ecosystem import wandb
from weave.legacy.weave.show import show_url

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

panel: weave.legacy.weave.panels.Group = weave.legacy.weave.panels.Group(
    items={
        "scatter": wandb.Scatter(  # type: ignore
            data, x_fn=lambda item: item["a"], y_fn=lambda item: item["b"]
        ),
        "table": lambda scatter: weave.legacy.weave.panels.LabeledItem(
            label="Selected items",
            item=weave.legacy.weave.panels.Group(
                style="height: 400px;",
                preferHorizontal=True,
                items={"table": scatter.selected()},
            ),
        ),
    }
)

print(show_url(panel))
