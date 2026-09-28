"""Token accounting shared by agent span filters and statistics."""


def total_tokens_sql(table_alias: str) -> str:
    """Prefer a reported total, including zero, over the legacy component sum."""
    attrs = f"{table_alias}.custom_attrs_int"
    reported = f"{attrs}['gen_ai.usage.total_tokens']"
    return (
        f"toFloat64(if(mapContains({attrs}, 'gen_ai.usage.total_tokens') "
        f"AND {reported} >= 0, toUInt64({reported}), "
        f"{table_alias}.input_tokens + {table_alias}.output_tokens + "
        f"{table_alias}.reasoning_tokens))"
    )
