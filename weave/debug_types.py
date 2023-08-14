import textwrap

from .weave_types import *
from .language_features.tagging import tagged_value_type


def short_type(type: Type) -> str:
    s = type.__repr__()
    if len(s) > 40:
        s = s[:40] + "..."
    return f"<{s}>"


def why_not_assignable(to_type: Type, from_type: Type) -> typing.Optional[str]:
    """Returns None if assignable, otherwise a string explaining why not.

    This is the start of a the implementation, however, it is not yet complete.
    """
    reasons: list[str] = []
    if to_type == Any() or from_type == Any():
        return None
    elif isinstance(from_type, UnionType):
        for from_member in from_type.members:
            reason = why_not_assignable(to_type, from_member)
            if reason is not None:
                reasons.append(reason)
    elif isinstance(to_type, UnionType):
        for to_member in to_type.members:
            reason = why_not_assignable(to_member, from_type)
            if reason is None:
                return None
            reasons.append(f"{short_type(to_member)}: {reason}")

    elif isinstance(from_type, tagged_value_type.TaggedValueType) and not isinstance(
        to_type, tagged_value_type.TaggedValueType
    ):
        reason = why_not_assignable(to_type, from_type.value)
        if reason is not None:
            reasons.append(reason)

    elif isinstance(from_type, Const) and not isinstance(to_type, Const):
        reason = why_not_assignable(to_type, from_type.val_type)
        if reason is not None:
            reasons.append(reason)

    elif not isinstance(from_type, Const) and isinstance(to_type, Const):
        # Weird const behavior, allow assigning non-const to const (see weave_types)
        reason = why_not_assignable(to_type.val_type, from_type)
        if reason is not None:
            reasons.append(reason)

    elif isinstance(from_type, Function) and not isinstance(to_type, Function):
        reason = why_not_assignable(to_type, from_type.output_type)
        if reason is not None:
            reasons.append(reason)

    elif isinstance(from_type, TypedDict) and isinstance(to_type, Dict):
        for k, from_td_type in from_type.property_types.items():
            sub_reason = why_not_assignable(to_type.object_type, from_td_type)
            if sub_reason is not None:
                reasons.append(
                    f"Property {k} is not assignable\n{textwrap.indent(sub_reason, '  ')}"
                )

    elif isinstance(from_type, TypedDict) and isinstance(to_type, TypedDict):
        for k, to_type_type in to_type.property_types.items():
            from_type_type = from_type.property_types.get(k)
            if from_type_type is None:
                reasons.append(f"Missing property {k}")
            else:
                sub_reason = why_not_assignable(to_type_type, from_type_type)
                if sub_reason is not None:
                    reasons.append(
                        f"Property {k} is not assignable\n{textwrap.indent(sub_reason, '  ')}"
                    )

    elif to_type.name == from_type.name:
        type_vars = to_type.type_vars
        for k, to_type_type in type_vars.items():
            from_type_type = getattr(from_type, k)
            if from_type_type is None:
                reasons.append(f"Missing property {k}")
            else:
                sub_reason = why_not_assignable(to_type_type, from_type_type)
                if sub_reason is not None:
                    reasons.append(
                        f"Property {k} is not assignable\n{textwrap.indent(sub_reason, '  ')}"
                    )
    else:
        reasons.append("Incompatible types")
    if reasons:
        indented_reasons = textwrap.indent("\n".join(reasons), "  ")
        return f"{short_type(to_type)} !<- {short_type(from_type)}\n{indented_reasons}"

    # Check if our implementation above matches the actual assignability
    # implementation.
    is_assignable = to_type.assign_type(from_type)
    if reasons and is_assignable:
        print(
            "why_not_assignable programming error. reasons but assignable",
            to_type,
            from_type,
            reasons,
        )
    elif not reasons and not is_assignable:
        print(
            "why_not_assignable programming error. no reasons but not assignable",
            to_type,
            from_type,
            reasons,
        )

    return None
