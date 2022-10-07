import weave
import requests
import typing


@weave.type()
class SlurmJob:
    job_id: str
    comment: str
    job_state: str
    cluster: str
    job_name: str
    account: str
    cost: int
    cost_cpus: int
    submit_time: int
    start_time: int
    end_time: int


@weave.op()
def cost_by_user(jobs: weave.Node[list[SlurmJob]]) -> weave.panels.Plot:
    plot = weave.panels.Plot(jobs)
    plot.set_x(lambda r: r.cost_cpus)
    plot.set_y(lambda r: r.account)
    return plot


@weave.op()
def time_by_user(jobs: weave.Node[list[SlurmJob]]) -> weave.panels.Plot:
    plot = weave.panels.Plot(jobs)
    plot.set_x(lambda r: r.end_time - r.start_time)
    plot.set_y(lambda r: r.account)
    return plot


@weave.op()
def jobs_render2(
    jobs: weave.Node[list[SlurmJob]],
) -> weave.panels.Table:
    return weave.panels.Table(
        jobs,
        pd_columns={
            "job_id": lambda j: j.job_id,
            "comment": lambda j: j.comment,
            "job_state": lambda j: j.job_state,
            "submit_time": lambda j: j.submit_time,
            "cluster": lambda j: j.cluster,
            "job_name": lambda j: j.job_name,
            "account": lambda j: j.account,
            "cost": lambda j: j.cost,
            "cost_cpus": lambda j: j.cost_cpus,
            "start_time": lambda j: j.start_time,
            "end_time": lambda j: j.end_time,
            "elapsed_time": lambda j: j.end_time - j.start_time,
        },
    )


@weave.op()
def jobs_render(
    jobs: weave.Node[list[SlurmJob]],
) -> weave.panels.Table:
    return weave.panels.Table(
        jobs,
        pd_columns={
            "job_id": lambda j: j.job_id,
            "comment": lambda j: j.comment,
            "job_state": lambda j: j.job_state,
            "submit_time": lambda j: j.submit_time,
            "cluster": lambda j: j.cluster,
            "job_name": lambda j: j.job_name,
            "account": lambda j: j.account,
            "cost": lambda j: j.cost,
            "cost_cpus": lambda j: j.cost_cpus,
            "start_time": lambda j: j.start_time,
            "end_time": lambda j: j.end_time,
            "elapsed_time": lambda j: j.end_time - j.start_time,
        },
    )


@weave.type()
class SlurmNode:
    node_name: str
    state: str


# @weave.type()
# class SlurmJobStats:
#     jobs_submitted: int
#     jobs_started: int
#     jobs_completed: int
#     jobs_canceled: int
#     jobs_failed: int
#     jobs_pending: int
#     jobs_running: int


# @weave.op()
# def job_stats_render_chart(
#     job_stats: weave.Node[list[SlurmJobStats]],
# ) -> weave.panels.Plot:
#     plot = weave.panels.Plot(job_stats)
#     plot.set_x(lambda r: r.jobs_started)
#     plot.set_y(lambda r: r.jobs_completed)
#     plot.set_mark("bar")
#     return plot


# @weave.op()
# def job_stats_render(job_stats: weave.Node[list[SlurmJobStats]]) -> weave.panels.Table:
#     return weave.panels.Table(
#         job_stats,
#         pd_columns={
#             "jobs_submitted": lambda j: j.jobs_submitted,
#             "jobs_started": lambda j: j.jobs_started,
#             "jobs_completed": lambda j: j.jobs_completed,
#             "jobs_canceled": lambda j: j.jobs_canceled,
#             "jobs_failed": lambda j: j.jobs_failed,
#             "jobs_pending": lambda j: j.jobs_pending,
#             "jobs_running": lambda j: j.jobs_running,
#         },
#     )


@weave.op()
def nodes_render(
    nodes: weave.Node[list[SlurmNode]],
) -> weave.panels.Table:
    return weave.panels.Table(
        nodes,
        pd_columns={"node_name": lambda n: n.node_name, "state": lambda n: n.state},
    )


def null_if_zero(x):
    return x if x != 0 else None


@weave.type()
class Slurm:
    restapi_url: str

    # diags = []

    @property
    def full_url(self):
        return self.restapi_url + "/slurm/v0.0.37"

    @weave.op(pure=False)
    def jobs(self) -> list[SlurmJob]:
        resp = requests.get(self.full_url + "/jobs")
        jobs = resp.json()["jobs"]

        return [
            SlurmJob(
                job_id=j["job_id"],
                cluster=j["cluster"],
                job_name=j["name"],
                account=j["account"],
                cost=j["billable_tres"],
                cost_cpus=j["cpus"],
                comment=j["comment"],
                job_state=j["job_state"],
                submit_time=null_if_zero(j["submit_time"]),
                start_time=null_if_zero(j["start_time"]),
                end_time=null_if_zero(j["end_time"]),
            )
            for j in reversed(jobs)
        ]

    @weave.op(pure=False)
    def nodes(self) -> list[SlurmNode]:
        resp = requests.get(self.full_url + "/nodes")
        nodes = resp.json()["nodes"]

        return [
            SlurmNode(node_name=n["name"], state=n["state"]) for n in reversed(nodes)
        ]

    # @weave.op(pure=False)
    # def job_stats(self) -> list[SlurmJobStats]:
    #     resp = requests.get(self.full_url + "/diag")
    #     self.diags.append(resp.json()["statistics"])
    #     return [
    #         SlurmJobStats(
    #             jobs_submitted=d["jobs_submitted"],
    #             jobs_started=d["jobs_started"],
    #             jobs_completed=d["jobs_completed"],
    #             jobs_canceled=d["jobs_canceled"],
    #             jobs_failed=d["jobs_failed"],
    #             jobs_pending=d["jobs_pending"],
    #             jobs_running=d["jobs_running"],
    #         )
    #         for d in reversed(self.diags)
    #     ]


@weave.op(render_info={"type": "function"})
def slurm(restapi_url: str) -> Slurm:
    return Slurm(restapi_url)


@weave.op()
def slurm_render7(
    slurm_node: weave.Node[Slurm],
) -> weave.panels.Card:
    slurm = typing.cast(Slurm, slurm_node)
    return weave.panels.Card(
        title="slurm",
        subtitle="",
        content=[
            weave.panels.CardTab(
                name="Overview",
                content=weave.panels.Group(
                    prefer_horizontal=True,
                    items=[
                        weave.panels.LabeledItem(
                            item=slurm.jobs().count(), label="Total jobs"
                        ),
                        weave.panels.LabeledItem(
                            item=slurm.nodes().count(), label="Total nodes"
                        ),
                    ],
                ),
            ),
            weave.panels.CardTab(
                name="Costs",
                content=weave.panels.Group(
                    prefer_horizontal=True,
                    items=[
                        weave.panels.LabeledItem(
                            item=slurm.jobs(), label="Cost by user"
                        ),
                        weave.panels.LabeledItem(
                            item=slurm.jobs(), label="Time by user"
                        ),
                    ],
                ),
            ),
            weave.panels.CardTab(name="Nodes", content=slurm.nodes()),
            weave.panels.CardTab(name="Jobs", content=slurm.jobs()),
            # weave.panels.CardTab(name="JobStats", content=slurm.job_stats()),
        ],
    )
