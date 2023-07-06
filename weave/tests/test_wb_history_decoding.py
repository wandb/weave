import datetime
import time
import weave
from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun
from weave.wandb_client_api import wandb_gql_query, wandb_public_api


# def test_history_logging(user_by_api_key_in_env):
def test_history_logging():
    rows = [{"a": 1}]
    run = InMemoryLazyLiteRun(project_name="dev_test_weave_ci")

    total_rows = []

    all_keys = set()
    for row in rows:
        run.log(row)
        new_row = {
            "_step": len(total_rows),
            "_timestamp": datetime.datetime.now().timestamp(),
            **row,
        }
        total_rows.append(new_row)
        all_keys.update(list(row.keys()))

    row_type = weave.types.TypeRegistry.type_of([{}, *total_rows])
    run_node = weave.ops.project(run._entity_name, run._project_name).run(run._run_name)

    def do_assertion():
        history_node = run_node.history2()
        assert row_type.assign_type(history_node.type)

        for key in all_keys:
            column_node = history_node[key]
            column_value = weave.use(column_node).to_pylist_raw()
            assert column_value == [row.get(key) for row in total_rows]

    def history_is_uploaded():
        history = get_raw_gorilla_history(
            run._entity_name, run._project_name, run._run_name
        )
        return (
            len(history.get("liveData", [])) == len(total_rows)
            and history.get("parquetUrls") == []
        )

    def history_is_compacted():
        history = get_raw_gorilla_history(
            run._entity_name, run._project_name, run._run_name
        )
        return history.get("liveData") == [] and len(history.get("parquetUrls", [])) > 0

    # First assertion is with liveset
    wait_for_x_times(history_is_uploaded)
    do_assertion()

    # Second assertion is with parquet files
    run.finish()
    # Sad...can't quite figure this out
    # ensure_history_compaction_runs(run._entity_name, run._project_name, run._run_name)
    wait_for_x_times(history_is_compacted)
    do_assertion()


def wait_for_x_times(for_fn, times=10, wait=1):
    done = False
    while times > 0 and not done:
        times -= 1
        done = for_fn()
        time.sleep(wait)
    assert times > 0


def get_raw_gorilla_history(entity_name, project_name, run_name):
    query = """query WeavePythonCG($entityName: String!, $projectName: String!, $runName: String! ) {
            project(name: $projectName, entityName: $entityName) {
                run(name: $runName) {
                    # historyKeys
                    parquetHistory(liveKeys: ["_timestamp"]) {
                        liveData
                        parquetUrls
                    }
                }
            }
    }"""
    variables = {
        "entityName": entity_name,
        "projectName": project_name,
        "runName": run_name,
    }
    res = wandb_gql_query(query, variables)
    return res.get("project", {}).get("run", {}).get("parquetHistory", {})


def ensure_history_compaction_runs(entity_name, project_name, run_name):
    client = wandb_public_api().client
    # original_url = client._client.transport.url
    # original_schema = client._client.schema
    # client._client.transport.url = "http://localhost:8080/admin/parquet_workflow"

    test_api_key = wandb_public_api().api_key

    post_args = {
        "headers": client._client.transport.headers,
        "cookies": client._client.transport.cookies,
        "auth": ("api", test_api_key),
        "timeout": client._client.transport.default_timeout,
        "data": {
            "task_type": "export_history_to_parquet",
            "run_key": {
                "entity_name": entity_name,
                "project_name": project_name,
                "run_name": run_name,
            },
        },
    }
    request = client._client.transport.session.post(
        "http://localhost:8080/admin/parquet_workflow", **post_args
    )

    print(request)

    client.execute()

    # client._client.transport.url = original_url
    # client._client.schema = original_schema
