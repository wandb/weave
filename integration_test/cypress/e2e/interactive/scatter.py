import random
import weave
from weave.ecosystem import wandb

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

panel: weave.panels.Group2 = weave.panels.Group2(
    items={
        "scatter": wandb.Scatter(
            data, x_fn=lambda item: item["a"], y_fn=lambda item: item["b"]
        ),
        "table": lambda scatter: weave.panels.LabeledItem(
            label="Selected items",
            item=weave.panels.Group2(
                style="height: 400px;",
                preferHorizontal=True,
                items={"table": scatter.selected()},
            ),
        ),
    }
)

print(weave.show_url(panel))
