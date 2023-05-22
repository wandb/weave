# Cache policy for when cache mode is minimal.
# We don't declare these directly on op defs for now. I want op definitions
# to be more declarative than that. Ie they should be cached if they are
# known to be expensive, either because of an API call that costs $ or
# requiring a lot of compute/memory.

# These operate on "simple_name" (non uri name), which is called "full_name"
# by graph.py


def should_table_cache(op_name: str) -> bool:
    # Cache the results of this op in a single run table. This is experimental
    # and not actually safe in a distributed environment. If there multiple
    # writers write in parallel to a table use weave mutations, only one
    # will succeed. Since runs are cached by user right now, this just means
    # that if the user makes parallel requests that require table caching,
    # only one of the requests values will make it into the cache.
    return (
        op_name == "op-expensive_op"
        or op_name == "BaseRetrievalQA-run"
        or op_name == "BaseChatModel-predict"
        or op_name == "op-stable_diffusion"
        or op_name == "op-img2prompt"
    )


def should_cache(op_name: str) -> bool:
    return not op_name.startswith("mapped") and (
        op_name.endswith("file-table")
        or op_name.endswith("file-joinedTable")
        or op_name.endswith("readcsv")
        or op_name.endswith("table-2DProjection")
        or op_name.endswith("ArrowWeaveList-2DProjection")
        or op_name.endswith("faiss_from_documents")
        or op_name == "FAISS-document_embeddings"
        or should_table_cache(op_name)
    )
