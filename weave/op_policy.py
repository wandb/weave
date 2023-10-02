# Cache policy for when cache mode is minimal.
# We don't declare these directly on op defs for now. I want op definitions
# to be more declarative than that. Ie they should be cached if they are
# known to be expensive, either because of an API call that costs $ or
# requiring a lot of compute/memory.

# These operate on "simple_name" (non uri name), which is called "full_name"
# by graph.py


CACHE_AND_PARALLEL_OP_NAMES = [
    "op-expensive_op",
    "Chain-run",
    "BaseChatModel-predict",
    "op-stable_diffusion",
    "op-img2prompt",
]

CACHE_NON_PURE_OP_NAMES = [
    "gqlroot-wbgqlquery",
    "get",
]

CACHE_OP_NAMES = (
    [
        "file-readcsv",
        "op-run_chain",
        "table-2DProjection",
        "table-projection2D",
        "ArrowWeaveList-2DProjection",
        "ArrowWeaveList-projection2D",
        "op-faiss_from_documents",
        "FAISS-document_embeddings",
        "HuggingFacePackage-model",
        "HFModelTextClassification-pipeline",
        "HFModelTextClassification-call",
        # These are parallelized by derive_op only, in a custom way
        # Should move them to CACHE_AND_PARALLEL_OP_NAMES once that
        # is fixed.
        "file-partitionedTable",
        "file-table",
        "file-joinedTable",
        "op-umap_project",
        "op-openai_embed",
        "op-hdbscan_cluster",
        "wb_trace_tree-convertToSpans",
    ]
    + CACHE_AND_PARALLEL_OP_NAMES
    + CACHE_NON_PURE_OP_NAMES
)

ARROW_FS_OPS = ["run-history3", "run-history3_with_columns", "table-rows"]


# history ops are parallelized by derive_op only, in a custom way
# PARALLEL_OP_NAMES = ["run-history", "run-history2"] + CACHE_AND_PARALLEL_OP_NAMES
PARALLEL_OP_NAMES = CACHE_AND_PARALLEL_OP_NAMES


def should_run_in_parallel(op_name: str) -> bool:
    if op_name.startswith("mapped_"):
        op_name = op_name[len("mapped_") :]
    return op_name in PARALLEL_OP_NAMES


def should_cache(op_name: str) -> bool:
    if op_name.startswith("mapped_"):
        return False
    return op_name in CACHE_OP_NAMES


def should_table_cache(op_name: str) -> bool:
    return False
