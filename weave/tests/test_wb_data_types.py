import pytest
import wandb
from wandb import data_types as wb_data_types
import numpy as np
from wandb.sdk.data_types._dtypes import TypeRegistry as SDKTypeRegistry
from wandb.sdk.data_types.helper_types.classes import Classes as SDKClasses

from .fixture_fakewandb import FakeApi

from ..wandb_util import weave0_type_json_to_weave1_type
from ..ops_domain import wb_domain_types
import weave
from .. import weave_types as types
import datetime
from bokeh.plotting import figure
import os

from wandb.apis.public import Artifact as PublicArtifact


class RandomClass:
    pass


def make_image():
    return wandb.Image(np.random.randint(0, 255, (32, 32)))


def make_audio():
    return wandb.Audio(np.random.uniform(-1, 1, 44100), 44100)


def make_html():
    return wandb.Html("<html><body><h1>Hello</h1></body></html>")


def make_bokeh():
    x = [1, 2, 3, 4, 5]
    y = [6, 7, 2, 4, 5]
    p = figure(title="simple line example", x_axis_label="x", y_axis_label="y")
    p.line(x, y, legend_label="Temp.", line_width=2)
    return wb_data_types.Bokeh(p)


def make_video():
    with open("video.mp4", "w") as f:
        f.write("00000")
    vid = wandb.Video("video.mp4")
    os.remove("video.mp4")
    return vid


def make_object3d():
    return wandb.Object3D(
        np.array(
            [
                [0, 0, 0, 1],
                [0, 0, 1, 13],
                [0, 1, 0, 2],
                [0, 1, 0, 4],
            ]
        )
    )


def make_molecule():
    with open("test_mol.pdb", "w") as f:
        f.write("00000")
    mol = wandb.Molecule("test_mol.pdb")
    os.remove("test_mol.pdb")
    return mol


@pytest.mark.parametrize(
    "sdk_obj, expected_type",
    [
        #
        # Primitive Types
        #
        (None, types.none_type),
        (True, types.Boolean()),
        (42, types.Float()),
        ("hello", types.String()),
        #
        # Container Types
        #
        ({"hello": "world"}, types.TypedDict({"hello": types.String()})),
        ([1, 2, 3], types.List(types.Float())),
        ([{"hello": "world"}], types.List(types.TypedDict({"hello": types.String()}))),
        #
        # Domain Types
        #
        (datetime.datetime.now(), types.Datetime()),  # type: ignore
        # See comment in wandb_util.py - this may change in the future
        (np.array([1, 2, 3]), types.NoneType()),
        #
        # Media Types
        #
        (
            make_image(),
            weave.ops.ImageArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_audio(),
            weave.ops.AudioArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_html(),
            weave.ops.HtmlArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_bokeh(),
            weave.ops.BokehArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_video(),
            weave.ops.VideoArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_object3d(),
            weave.ops.Object3DArtifactFileRef.WeaveType(),  # type: ignore
        ),
        (
            make_molecule(),
            weave.ops.MoleculeArtifactFileRef.WeaveType(),  # type: ignore
        ),
        # See comment in wandb_util.py - this may change in the future
        (
            SDKClasses([{"id": 1, "name": "foo"}]),
            types.Number(),
        ),
        #
        # Table Types
        # Leaving the table/key types out for now since there are not code paths
        # that exersize this. We will likely need to add these in the future,
        # but in the interest of incremental PRs, I'm leaving them out
        # TODO: 3 table Types: wandb_data_types._TableType, wandb_data_types._JoinedTableType, wandb_data_types._PartitionedTableType
        # TODO: 3 key Types:  wandb_data_types._PrimaryKeyType, wandb_data_types._ForeignKeyType, wandb_data_types._ForeignIndexType
        #
        # Legacy Fallback Types
        #
        (RandomClass(), types.UnknownType()),
    ],
)
def test_image(sdk_obj, expected_type, fake_wandb):
    art = wandb.Artifact("test", "test")
    obj_json = SDKTypeRegistry.type_of(sdk_obj).to_json(art)

    # Create an artifact that looks like it was loaded remotely so we can use it without mocking backend
    api = FakeApi()
    logged_artifact = PublicArtifact(
        api.client,
        "test",
        "test",
        "test",
        {
            "id": "1234567890",
            "artifactSequence": {
                "name": "test",
            },
            "digest": art.digest,
            "aliases": [],
        },
    )
    logged_artifact._manifest = art.manifest
    art._logged_artifact = logged_artifact

    assert weave0_type_json_to_weave1_type(obj_json, art) == expected_type
