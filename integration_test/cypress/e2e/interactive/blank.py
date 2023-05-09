import random
import weave
from weave.ecosystem import wandb

weave.use_fixed_server_port()

items = weave.save([1])

print(weave.show_url(items))
