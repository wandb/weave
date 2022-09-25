import weave
import requests
import typing


@weave.type()
class SlurmJob:
    job_id: str
    comment: str
    job_state: str

    submit_time: int
    start_time: int
    end_time: int


@weave.op()
def jobs_render(
    jobs: weave.Node[list[SlurmJob]],
) -> weave.panels.Table:
    return weave.panels.Table(
        jobs,
        columns=[
            lambda job: job.job_id,
            lambda job: job.comment,
            lambda job: job.job_state,
            lambda job: job.submit_time,
            lambda job: job.start_time,
            lambda job: job.end_time,
            lambda job: job.end_time - job.start_time,
        ],
    )


@weave.type()
class SlurmNode:
    node_name: str
    state: str


@weave.op()
def nodes_render(
    nodes: weave.Node[list[SlurmNode]],
) -> weave.panels.Table:
    return weave.panels.Table(
        nodes,
        columns=[
            lambda node: node.node_name,
            lambda node: node.state,
        ],
    )


@weave.type()
class Slurm:
    restapi_url: str

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
                comment=j["comment"],
                job_state=j["job_state"],
                submit_time=j["submit_time"],
                start_time=j["start_time"],
                end_time=j["end_time"],
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


@weave.op(render_info={"type": "function"})
def slurm(restapi_url: str) -> Slurm:
    return Slurm(restapi_url)


@weave.op()
def slurm_render(
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
            weave.panels.CardTab(name="Nodes", content=slurm.nodes()),
            weave.panels.CardTab(name="Jobs", content=slurm.jobs()),
        ],
    )
