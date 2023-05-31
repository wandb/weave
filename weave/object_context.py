# This is essentially a transaction manager and we may want to rename it.
# You can create it, then any mutations you make to objects within the context
# will be collected, and only written when the context exits.
# Can be used with weave_api.finish() to batch mutations from user code.
#
# Its experimental for now.

import contextvars
import typing
import contextlib
import dataclasses
import typing
from typing import Any

if typing.TYPE_CHECKING:
    from . import ref_base

from . import weave_types as types
from . import box
from . import uris


@dataclasses.dataclass
class MutationRecord:
    mutation_name: str
    args: typing.List[typing.Any]


@dataclasses.dataclass
class ObjectRecord:
    val: typing.Any
    type: types.Type
    branched_from_uri: typing.Optional[str] = None
    mutations: typing.List[MutationRecord] = dataclasses.field(default_factory=list)


class NoResult:
    pass


@dataclasses.dataclass
class ObjectContext:
    objects: dict[str, ObjectRecord] = dataclasses.field(default_factory=dict)

    def add_ref(self, target_uri: str, val: typing.Any, type: types.Type) -> None:
        self.objects[target_uri] = ObjectRecord(val, type)

    def lookup_ref_val(self, target_uri: str) -> typing.Any:
        if target_uri not in self.objects:
            return NoResult()
        return self.objects[target_uri].val

    def lookup_ref_type(self, target_uri: str) -> typing.Union[types.Type, NoResult]:
        if target_uri not in self.objects:
            return NoResult()
        return self.objects[target_uri].type

    def add_mutation(
        self,
        target_uri: str,
        source_uri: str,
        new_val: typing.Any,
        make_new_type: typing.Callable[[types.Type], types.Type],
        mutation: typing.Any,
    ) -> None:
        branched_from_uri = None
        if source_uri != target_uri:
            branched_from_uri = source_uri

        source_record = self.objects.get(source_uri)
        if branched_from_uri is not None and source_record is None:
            raise ValueError("Can't branch object that doesn't exist")

        target_record = self.objects.get(target_uri)
        if target_record is None:
            self.objects[target_uri] = ObjectRecord(
                new_val,
                make_new_type(types.UnknownType()),
                branched_from_uri,
                mutations=[mutation],
            )
        else:
            self.objects[target_uri].val = new_val
            self.objects[target_uri].type = make_new_type(target_record.type)
            if branched_from_uri is not None:
                # we're overwriting a target with a new branch, so reset
                # mutations
                self.objects[target_uri].mutations = [mutation]
            else:
                self.objects[target_uri].mutations.append(mutation)

    def finish_mutation(self, target_uri: str) -> None:
        from . import artifact_fs, artifact_local, artifact_wandb

        target_record = self.objects.get(target_uri)
        if target_record is None:
            raise ValueError("No object to finish mutation on")
        if not target_record.mutations:
            return

        if target_record.branched_from_uri is None:
            source_uri = uris.WeaveURI.parse(target_uri)
            art = artifact_local.LocalArtifact(source_uri.name, source_uri.version)
        else:
            source_uri = uris.WeaveURI.parse(target_record.branched_from_uri)
            # Note: the mutation bookeeping is done at the individual object level,
            # so the path component is often non-empty. However, since we are managing
            # state at the artifact level, we need to ensure the path is empty to conform
            # to the expectations of the branching logic.
            source_uri.path = ""  # type: ignore
            art = artifact_local.LocalArtifact.fork_from_uri(source_uri)  # type: ignore

        obj = box.box(target_record.val)
        target_branch = uris.WeaveURI.parse(target_uri).version
        if target_branch is None:
            raise ValueError("No branch to finish mutation on")

        from weave import artifact_wandb

        # Hack: if the target branch looks like a commit hash, then we
        # don't want to use it as a branch - this is the case that we are
        # mutating an artifact directly without a branch. Seems like we
        # might want to put this logic elsewhere, but for now this works.
        if artifact_wandb.likely_commit_hash(target_branch):
            target_branch = None
        weave_type = types.TypeRegistry.type_of(obj)
        ref = art.set("obj", weave_type, obj)
        artifact_fs.update_weave_meta(weave_type, art)
        art.save(branch=target_branch)  # type: ignore

    def finish_mutations(self) -> None:
        for target_uri in self.objects.keys():
            self.finish_mutation(target_uri)


_object_context: contextvars.ContextVar[
    typing.Optional[ObjectContext]
] = contextvars.ContextVar("_object_context", default=None)


@contextlib.contextmanager
def object_context() -> typing.Iterator[ObjectContext]:
    ctx = _object_context.get()
    token = None
    if ctx is None:
        ctx = ObjectContext()
        token = _object_context.set(ctx)
    try:
        yield ctx
    finally:
        if token is not None:
            _object_context.reset(token)
            ctx.finish_mutations()


def get_object_context() -> typing.Optional[ObjectContext]:
    return _object_context.get()
