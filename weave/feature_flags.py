# Enables projection pushdown for get(*)->AWL queries.
# This is disabled in prod and unit tests for now.
# There are a few things to fix
#    - some failing tests
#    - decide final "extra" format for specifying loading columns from an artifact list
# We can enable it when it becomes necessary, which will happen if we ship any code where
# we want users to save thousands of columns inside AWLs that they have.
# I ran into it as I was messing with and testing other perf stuff.
# Note we already do projection pushdown for StreamTable and wandb history read code paths.
# We just don't do it on AWLs that users save directly (but this feature flag enables that)
#
# Without this, thousands of columns and hundreds of thousand plus rows within an AWL gets really slow.
# With this its nice and fast!
GET_AWL_PROJECTION_PUSHDOWN = False
