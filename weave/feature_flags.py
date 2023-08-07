# Enables projection pushdown for get(*)->AWL queries.
# This is disabled in prod and unit tests for now.
# There are a few things to fix
#    - some failing tests
#    - decide final "extra" format for specifying loading columns from an artifact list
GET_AWL_PROJECTION_PUSHDOWN = False
