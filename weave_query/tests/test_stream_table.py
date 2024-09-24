import os
import time

from weave.legacy.weave.wandb_interface.wandb_stream_table import StreamTable


def main(table_name, project_name, entity_name, sample_limit, gap_ms):
    st = StreamTable(
        table_name,
        project_name=project_name,
        entity_name=entity_name,
    )

    for i in range(sample_limit):
        time.sleep(gap_ms / 1000)
        st.log({"val": i})
        print({"val": i})

    st.finish()


if __name__ == "__main__":
    main(
        os.environ.get("TABLE_NAME", "stream"),
        os.environ.get("PROJECT_NAME", "stream_test"),
        os.environ.get("ENTITY_NAME", "timssweeney"),
        int(os.environ.get("SAMPLE_LIMIT", 1000)),
        int(os.environ.get("GAP_MS", 250)),
    )
