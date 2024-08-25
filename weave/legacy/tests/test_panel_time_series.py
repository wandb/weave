import time

import wandb

import weave
from weave.legacy.weave.ecosystem.wandb.panel_time_series import TimeSeries


def test_panel_timeseries(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    for i in range(10):
        time.sleep(0.2)
        run.log({"val": i, "cat": str(i % 2)})
    run.finish()

    history_node = (
        weave.legacy.weave.ops.project(run.entity, run.project).run(run.id).history2()
    )
    panel = TimeSeries(history_node)
    init_config_node = panel.initialize()
    init_config = weave.use(init_config_node)
    panel.config = init_config
    render_node = panel.render()
    res = weave.use(render_node)
    # What to assert here? Should we be getting .contents?
    assert res != None
