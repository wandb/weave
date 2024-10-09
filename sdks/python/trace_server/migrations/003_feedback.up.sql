CREATE TABLE feedback (
    /*
    `id`: The unique identifier for the feedback. This is a UUID.
    */
    id String,

    /*
    `project_id`: The project identifier for the ref. This is an internal
    identifier that matches the project identifier in the W&B API.
    It is stored for feedback to allow efficient permissions filtering.
    */
    project_id String,

    /*
    `weave_ref`: The ref the feedback is associated with.
    Note: the weave prefix is to avoid conflict with React's notion of ref.
    */
    weave_ref String,

    /*
    `wb_user_id`: The ID of the user account used to authenticate the feedback creation.
    This is the ID of the user in the W&B API.
    */
    wb_user_id String,

    /*
    `creator`: The name to display for who the feedback came from. Can default to the name of
    the user account used to authenticate the feedback creation, but can be an arbitrary string.
    This is useful for feedback that originated with end users who may not have a W&B account.
    */
    creator String NULL,

    /*
    `created_at`: The time that the row was inserted into the database.
    */
    created_at DateTime64(3) DEFAULT now64(3),

    /*
    `feedback_type`: The type of feedback that was given. The prefix "wandb." is reserved for our use.
    */
    feedback_type String,

    /*
    `payload_dump`: A dictionary of values that represent the feedback.
    The schema of this dictionary is determined by the feedback_type.
    */
    payload_dump String,

) ENGINE = ReplacingMergeTree()
ORDER BY (project_id, weave_ref, wb_user_id, id);
