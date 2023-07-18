import gql

from ... import wandb_api


ARTIFACT_LINEAGE_QUERY = gql.gql(
    """
    query ArtifactLineage(
        $entityName: String!,
        $projectName: String!,
        $artifactName: String!,
    ) {
        project(name: $projectName, entityName: $entityName) {
            artifact(name: $artifactName) {
                artifactLineageDag(limit: 10000, filterGeneratedArtifacts: true) {
                    artifacts {
                        artifactNodeID
                        entityName
                        projectName
                        artifactTypeName
                        artifactSequenceName
                        artifactCommitHash
                        versionIndex
                    }
                    runs {
                        runNodeID
                        entityName
                        projectName
                        runName
                        displayName
                        jobType
                    }
                    edges {
                        edgeID
                        artifactNodeID
                        runNodeID
                        direction
                    }
                    hitLimit
                }
            }
        }
    }
    """
)


def get_run_checkpoint_chain(entity: str, project: str, leaf_checkpoint_name: str):
    api = wandb_api.WandbApi()

    query_res = api.query(
        ARTIFACT_LINEAGE_QUERY,
        entityName=entity,
        projectName=project,
        artifactName=leaf_checkpoint_name,
    )

    dag = query_res["project"]["artifact"]["artifactLineageDag"]

    artifacts_dict = {a["artifactNodeID"]: a for a in dag["artifacts"]}
    runs_dict = {r["runNodeID"]: r for r in dag["runs"]}

    target_artifact_id = [
        a["artifactNodeID"]
        for a in dag["artifacts"]
        if f"{a['artifactSequenceName']}:v{a['versionIndex']}" == leaf_checkpoint_name
    ][0]

    # Create an empty sequence list.
    sequence = []

    # Traverse the DAG from the target artifact.
    current_artifact_id = target_artifact_id

    while True:
        # Find edges where the artifact is the target and the direction is 'AwayFromArtifact'.
        next_edges = [
            e
            for e in dag["edges"]
            if e["artifactNodeID"] == current_artifact_id
            and e["direction"] == "TowardArtifact"
        ]

        # If there are no such edges, we've reached the beginning of the lineage.
        if not next_edges:
            break

        # Get the corresponding run for the current artifact.
        current_run_id = next_edges[0]["runNodeID"]
        sequence.append(
            (runs_dict[current_run_id], artifacts_dict[current_artifact_id])
        )

        # Find the next artifact(s) where the run is the source and the direction is 'AwayFromArtifact'.
        next_edges = [
            e
            for e in dag["edges"]
            if e["runNodeID"] == current_run_id and e["direction"] == "AwayFromArtifact"
        ]

        # Find the checkpoint artifact among the next artifacts.
        checkpoint_artifacts = [
            e
            for e in next_edges
            if artifacts_dict[e["artifactNodeID"]]["artifactTypeName"] == "checkpoint"
        ]

        # If there's no checkpoint artifact, we've reached the beginning of the lineage.
        if not checkpoint_artifacts:
            break

        # Set the next artifact to the checkpoint artifact (since there should be only one checkpoint artifact, get the first).
        current_artifact_id = checkpoint_artifacts[0]["artifactNodeID"]

    return sequence
