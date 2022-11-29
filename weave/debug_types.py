import textwrap

from .weave_types import *


def short_type(type: Type) -> str:
    s = type.__repr__()
    if len(s) > 20:
        s = s[:20] + "..."
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

    elif to_type.name == from_type.name:
        type_vars = to_type.type_vars()
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
        return f"Unhandled case: {short_type(to_type)} {short_type(from_type)}"
    if reasons:
        indented_reasons = textwrap.indent("\n".join(reasons), "  ")
        return f"why_not_assignable is not yet complete and may give you incorrect answers!\n\n{short_type(from_type)} !<- {short_type(to_type)}\n{indented_reasons}"
    return None
