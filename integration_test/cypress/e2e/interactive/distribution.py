import random
import weave
from weave.ecosystem import wandb

weave.use_fixed_server_port()

items = weave.save(
    [
        {
            "name": "x",
            "loss1": [random.gauss(5, 2) for i in range(500)],
            "loss2": [random.gauss(5, 2) for i in range(500)],
            "str_val": [random.choice(["a", "b", "c"]) for i in range(500)],
        },
        {
            "name": "y",
            "loss1": [random.gauss(9, 4) for i in range(500)],
            "loss2": [random.gauss(-1, 2) for i in range(500)],
            "str_val": [random.choice(["a", "b", "c"]) for i in range(500)],
        },
    ]
)

panel: wandb.Distribution = wandb.Distribution(items)

print(weave.show_url(panel))
