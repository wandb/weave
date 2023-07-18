import pytest
import wandb
from wandb import data_types as wb_data_types
import numpy as np
from wandb.sdk.data_types._dtypes import TypeRegistry as SDKTypeRegistry

from weave.language_features.tagging.tagged_value_type import TaggedValueType

from ..ops_primitives import file
from ..ops_domain.wbmedia import ImageArtifactFileRefType

from ..artifact_wandb import WandbArtifact, WeaveWBArtifactURI
from .. import artifact_fs

from .fixture_fakewandb import FakeApi

from ..wandb_util import weave0_type_json_to_weave1_type
import weave
from .. import weave_types as types
import datetime
from bokeh.plotting import figure
import os

from wandb.sdk.artifacts.public_artifact import Artifact as PublicArtifact


class RandomClass:
    pass


def make_image():
    return wandb.Image(np.random.randint(0, 255, (32, 32)))


def make_audio():
    return wandb.Audio(np.random.uniform(-1, 1, 44100), 44100)


HTML_STRING = "<body><h1>Hello this is some HTML with symbols and emoji '$!$!@#&#$%^??%$# 🤠</h1></body>"


def make_html():
    return wandb.Html(HTML_STRING)


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
        (42, types.Number()),
        ("hello", types.String()),
        #
        # Container Types
        #
        ({"hello": "world"}, types.TypedDict({"hello": types.String()})),
        ([1, 2, 3], types.List(types.Number())),
        ([{"hello": "world"}], types.List(types.TypedDict({"hello": types.String()}))),
        #
        # Domain Types
        #
        (datetime.datetime.now(), types.Timestamp()),  # type: ignore
        # See comment in wandb_util.py and https://github.com/wandb/weave/pull/140
        (np.array([1, 2, 3]), types.List(types.UnknownType())),
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
        # Temporarily disabled until we can figure out how to mock
        # types that need to reach into the artifact
        # (
        #     SDKClasses([{"id": 1, "name": "foo"}]),
        #     types.Number(),
        # ),
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

    assert weave0_type_json_to_weave1_type(obj_json) == expected_type


def make_table():
    def peak(v, m):
        return 1 - ((abs((2 * v) - m + 1) % m) / m)

    def make_np_image(dim=128):
        return np.array(
            [
                [(peak(col, dim) * peak(row, dim)) ** 0.5 for col in range(dim)]
                for row in range(dim)
            ]
        )

    def make_wb_image(use_middle=False, use_pixels=False):
        if use_pixels:
            position = (
                {
                    "middle": [50, 50],
                    "height": 10,
                    "width": 20,
                }
                if use_middle
                else {
                    "minX": 40,
                    "maxX": 100,
                    "minY": 30,
                    "maxY": 50,
                }
            )
            domain = "pixel"
        else:
            position = (
                {
                    "middle": [0.5, 0.5],
                    "height": 0.5,
                    "width": 0.25,
                }
                if use_middle
                else {
                    "minX": 0.4,
                    "maxX": 0.6,
                    "minY": 0.3,
                    "maxY": 0.7,
                }
            )
            domain = None
        return wandb.Image(
            make_np_image(),
            boxes={
                "box_set_1": {
                    "box_data": [
                        {
                            "position": position,
                            "domain": domain,
                            "class_id": 0,
                            "scores": {"loss": 0.3, "gain": 0.7},
                            "box_caption": "a",
                        },
                    ],
                },
                "box_set_2": {
                    "box_data": [
                        {
                            "position": position,
                            "domain": domain,
                            "class_id": 2,
                            "scores": {"loss": 0.3, "gain": 0.7},
                        },
                    ],
                },
            },
            masks={
                "mask_set_1": {
                    "mask_data": np.array(
                        [[row % 4 for col in range(128)] for row in range(128)]
                    )
                }
            },
            classes=[
                {"id": 0, "name": "c_zero"},
                {"id": 1, "name": "c_one"},
                {"id": 2, "name": "c_two"},
                {"id": 3, "name": "c_three"},
            ],
        )

    return wandb.Table(
        columns=["label", "image"],
        data=[
            ["a", make_wb_image(False, False)],
            ["b", make_wb_image(False, True)],
            ["c", make_wb_image(True, False)],
            ["d", make_wb_image(True, True)],
        ],
    )


def exp_raw_data(commit_hash: str):
    return [
        {
            "label": "a",
            "image": {
                "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{commit_hash}",
                "path": "media/images/724389f96d933f4166db.png",
                "format": "png",
                "height": 128,
                "width": 128,
                "sha256": "82287185f849c094e7acf82835f0ceeb8a5d512329e8ce1da12e21df2e81e739",
                "boxes": {
                    "box_set_1": [
                        {
                            "box_caption": "a",
                            "class_id": 0,
                            "domain": None,
                            "position": {
                                "maxX": 0.6,
                                "maxY": 0.7,
                                "minX": 0.4,
                                "minY": 0.3,
                                "height": None,
                                "middle": None,
                                "width": None,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                    "box_set_2": [
                        {
                            "box_caption": None,
                            "class_id": 2,
                            "domain": None,
                            "position": {
                                "maxX": 0.6,
                                "maxY": 0.7,
                                "minX": 0.4,
                                "minY": 0.3,
                                "height": None,
                                "middle": None,
                                "width": None,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                },
                "masks": {
                    "mask_set_1": {
                        "_type": "mask",
                        "path": "media/images/mask/b98a2fc054512bf6450c.mask.png",
                        "sha256": "00c619b2faa45fdc9ce6de014e7aef7839c9de725bf78b528ef47d279039aacf",
                    }
                },
            },
        },
        {
            "label": "b",
            "image": {
                "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{commit_hash}",
                "path": "media/images/724389f96d933f4166db.png",
                "format": "png",
                "height": 128,
                "width": 128,
                "sha256": "82287185f849c094e7acf82835f0ceeb8a5d512329e8ce1da12e21df2e81e739",
                "boxes": {
                    "box_set_1": [
                        {
                            "box_caption": "a",
                            "class_id": 0,
                            "domain": "pixel",
                            "position": {
                                "maxX": 100.0,
                                "maxY": 50.0,
                                "minX": 40.0,
                                "minY": 30.0,
                                "height": None,
                                "middle": None,
                                "width": None,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                    "box_set_2": [
                        {
                            "box_caption": None,
                            "class_id": 2,
                            "domain": "pixel",
                            "position": {
                                "maxX": 100.0,
                                "maxY": 50.0,
                                "minX": 40.0,
                                "minY": 30.0,
                                "height": None,
                                "middle": None,
                                "width": None,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                },
                "masks": {
                    "mask_set_1": {
                        "_type": "mask",
                        "path": "media/images/mask/b98a2fc054512bf6450c.mask.png",
                        "sha256": "00c619b2faa45fdc9ce6de014e7aef7839c9de725bf78b528ef47d279039aacf",
                    }
                },
            },
        },
        {
            "label": "c",
            "image": {
                "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{commit_hash}",
                "path": "media/images/724389f96d933f4166db.png",
                "format": "png",
                "height": 128,
                "width": 128,
                "sha256": "82287185f849c094e7acf82835f0ceeb8a5d512329e8ce1da12e21df2e81e739",
                "boxes": {
                    "box_set_1": [
                        {
                            "box_caption": "a",
                            "class_id": 0,
                            "domain": None,
                            "position": {
                                "maxX": None,
                                "maxY": None,
                                "minX": None,
                                "minY": None,
                                "height": 0.5,
                                "middle": [0.5, 0.5],
                                "width": 0.25,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                    "box_set_2": [
                        {
                            "box_caption": None,
                            "class_id": 2,
                            "domain": None,
                            "position": {
                                "maxX": None,
                                "maxY": None,
                                "minX": None,
                                "minY": None,
                                "height": 0.5,
                                "middle": [0.5, 0.5],
                                "width": 0.25,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                },
                "masks": {
                    "mask_set_1": {
                        "_type": "mask",
                        "path": "media/images/mask/b98a2fc054512bf6450c.mask.png",
                        "sha256": "00c619b2faa45fdc9ce6de014e7aef7839c9de725bf78b528ef47d279039aacf",
                    }
                },
            },
        },
        {
            "label": "d",
            "image": {
                "artifact": f"wandb-artifact:///test_entity/test_project/test_name:{commit_hash}",
                "path": "media/images/724389f96d933f4166db.png",
                "format": "png",
                "height": 128,
                "width": 128,
                "sha256": "82287185f849c094e7acf82835f0ceeb8a5d512329e8ce1da12e21df2e81e739",
                "boxes": {
                    "box_set_1": [
                        {
                            "box_caption": "a",
                            "class_id": 0,
                            "domain": "pixel",
                            "position": {
                                "maxX": None,
                                "maxY": None,
                                "minX": None,
                                "minY": None,
                                "height": 10.0,
                                "middle": [50.0, 50.0],
                                "width": 20.0,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                    "box_set_2": [
                        {
                            "box_caption": None,
                            "class_id": 2,
                            "domain": "pixel",
                            "position": {
                                "maxX": None,
                                "maxY": None,
                                "minX": None,
                                "minY": None,
                                "height": 10.0,
                                "middle": [50.0, 50.0],
                                "width": 20.0,
                            },
                            "scores": {"loss": 0.3, "gain": 0.7},
                        }
                    ],
                },
                "masks": {
                    "mask_set_1": {
                        "_type": "mask",
                        "path": "media/images/mask/b98a2fc054512bf6450c.mask.png",
                        "sha256": "00c619b2faa45fdc9ce6de014e7aef7839c9de725bf78b528ef47d279039aacf",
                    }
                },
            },
        },
    ]


def test_annotated_images_in_tables(fake_wandb):
    table = make_table()

    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)

    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    table_rows_type = table_node.rowsType()

    raw_data = weave.use(table_rows).to_pylist_notags()
    assert raw_data == exp_raw_data(art.commit_hash)

    ot = weave.use(table_rows_type).object_type
    assert ot == TaggedValueType(
        types.TypedDict(
            {"_ct_fake_run": types.String(), "_ct_fake_project": types.String()}
        ),
        weave.types.TypedDict(
            {
                "label": weave.types.UnionType(
                    weave.types.NoneType(), weave.types.String()
                ),
                "image": weave.types.UnionType(
                    ImageArtifactFileRefType(
                        boxLayers={"box_set_1": [0], "box_set_2": [2]},
                        boxScoreKeys=["loss", "gain"],
                        maskLayers={"mask_set_1": [0, 1, 2, 3]},
                        classMap={
                            "0": "c_zero",
                            "1": "c_one",
                            "2": "c_two",
                            "3": "c_three",
                        },
                    ),
                    weave.types.NoneType(),
                ),
            }
        ),
    )


def test_annotated_legacy_images_in_tables(fake_wandb):
    # Mocking this property makes the payload look like the legacy version.
    from wandb.data_types import _ImageFileType
    from wandb.sdk.data_types._dtypes import InvalidType

    def dummy_params(self):
        return {}

    def dummy_assign_type(self, wb_type=None):
        if isinstance(wb_type, _ImageFileType):
            return self
        return InvalidType()

    _ImageFileType.params = property(dummy_params)
    _ImageFileType.assign_type = dummy_assign_type

    table = make_table()

    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)

    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    table_rows_type = table_node.rowsType()

    raw_data = weave.use(table_rows).to_pylist_notags()
    assert raw_data == exp_raw_data(art.commit_hash)

    ot = weave.use(table_rows_type).object_type
    assert ot == TaggedValueType(
        types.TypedDict(
            {"_ct_fake_run": types.String(), "_ct_fake_project": types.String()}
        ),
        weave.types.TypedDict(
            {
                "label": weave.types.UnionType(
                    weave.types.NoneType(), weave.types.String()
                ),
                "image": weave.types.UnionType(
                    ImageArtifactFileRefType(
                        # Both box and mask layers have all the keys because
                        # we can't possible look at all the elements, so we assume
                        # they all may or may not have all the keys
                        boxLayers={
                            "box_set_1": [0, 1, 2, 3],
                            "box_set_2": [0, 1, 2, 3],
                        },
                        boxScoreKeys=["loss", "gain"],
                        maskLayers={"mask_set_1": [0, 1, 2, 3]},
                        classMap={
                            "0": "c_zero",
                            "2": "c_two",
                            "1": "c_one",
                            "3": "c_three",
                        },
                    ),
                    weave.types.NoneType(),
                ),
            }
        ),
    )


def make_simple_image_table():
    table = wandb.Table(columns=["label", "image"])
    for group in range(2):
        for item in range(3):
            table.add_data(
                f"{group}-{item}",
                wandb.Image(
                    np.ones((32, 32)) * group,
                    masks={
                        # Here, we add a mask set unique to each image to ensure that the mask is not considered in grouping
                        f"mask_set-{group}-{item}": {
                            "mask_data": np.array(
                                [[row % 4 for col in range(128)] for row in range(128)]
                            )
                        }
                    },
                ),
            )
    return table


def test_grouping_on_images(fake_wandb):
    table = make_simple_image_table()

    art = wandb.Artifact("test_name", "test_type")
    art.add(table, "table")
    art_node = fake_wandb.mock_artifact_as_node(art)

    file_node = art_node.file("table.table.json")
    table_node = file_node.table()
    table_rows = table_node.rows()
    grouped = table_rows.groupby(lambda row: weave.ops.dict_(g_image=row["image"]))

    raw_data = weave.use(grouped).to_pylist_notags()
    assert len(raw_data) == 2
    assert [[row["label"] for row in group] for group in raw_data] == [
        ["0-0", "0-1", "0-2"],
        ["1-0", "1-1", "1-2"],
    ]

    group_keys = weave.use(grouped.groupkey()).to_pylist_notags()
    assert [key["g_image"]["sha256"] for key in group_keys] == [
        "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
        "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    ]


exp_join2_labels = [
    ["0-0", "0-2"],
    ["0-0", "0-1"],
    ["0-0", "0-0"],
    ["0-1", "0-2"],
    ["0-1", "0-1"],
    ["0-1", "0-0"],
    ["0-2", "0-2"],
    ["0-2", "0-1"],
    ["0-2", "0-0"],
    ["1-0", "1-2"],
    ["1-0", "1-1"],
    ["1-0", "1-0"],
    ["1-1", "1-2"],
    ["1-1", "1-1"],
    ["1-1", "1-0"],
    ["1-2", "1-2"],
    ["1-2", "1-1"],
    ["1-2", "1-0"],
]

exp_join2_tag_shas = [
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
]

exp_joinall_labels = [
    ["0-0", "0-2"],
    ["0-0", "0-1"],
    ["0-0", "0-0"],
    ["0-1", "0-2"],
    ["0-1", "0-1"],
    ["0-1", "0-0"],
    ["0-2", "0-2"],
    ["0-2", "0-1"],
    ["0-2", "0-0"],
    ["1-0", "1-2"],
    ["1-0", "1-1"],
    ["1-0", "1-0"],
    ["1-1", "1-2"],
    ["1-1", "1-1"],
    ["1-1", "1-0"],
    ["1-2", "1-2"],
    ["1-2", "1-1"],
    ["1-2", "1-0"],
]

exp_joinall_tag_shas = [
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "1237db9e0c3d396728f7f4077f62b6283118c08fbfdced1e99e33205c270bd27",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
    "e7bdc527afd649f51950b4524b0c15aecaf7f484448a6cdfcdc2ecd9bba0f5a7",
]

exp_join_length = (3 * 3) * 2  # 3 copies of 2 unique images


def make_join_table_row_nodes(fake_wandb):
    table_1 = make_simple_image_table()
    table_2 = make_simple_image_table()

    art_1 = wandb.Artifact("test_name_1", "test_type_1")
    art_1.add(table_1, "table_1")

    art_2 = wandb.Artifact("test_name_2", "test_type_2")
    art_2.add(table_2, "table_2")

    art_1_node = fake_wandb.mock_artifact_as_node(art_1)
    art_2_node = fake_wandb.mock_artifact_as_node(art_2)

    file_1_node = art_1_node.file("table_1.table.json")
    table_1_node = file_1_node.table()
    table_1_rows = table_1_node.rows()

    file_2_node = art_2_node.file("table_2.table.json")
    table_2_node = file_2_node.table()
    table_2_rows = table_2_node.rows()

    return table_1_rows, table_2_rows


def test_join_all_on_images(fake_wandb):
    table_1_rows, table_2_rows = make_join_table_row_nodes(fake_wandb)

    rows = weave.ops.make_list(a=table_1_rows, b=table_2_rows)

    joined = rows.joinAll(lambda row: row["image"], True)

    raw_data = weave.use(joined).to_pylist_notags()
    assert len(raw_data) == exp_join_length
    assert [row["label"] for row in raw_data] == exp_joinall_labels

    group_keys = weave.use(joined.joinObj()).to_pylist_notags()
    assert [key["sha256"] for key in group_keys] == exp_joinall_tag_shas


def test_join_2_on_images(fake_wandb):
    table_1_rows, table_2_rows = make_join_table_row_nodes(fake_wandb)

    joined = table_1_rows.join(
        table_2_rows,
        lambda row: row["image"],
        lambda row: row["image"],
        "t1",
        "t2",
        True,
        True,
    )

    raw_data = weave.use(joined).to_pylist_notags()
    assert len(raw_data) == exp_join_length
    got = [[row["t1"]["label"], row["t2"]["label"]] for row in raw_data]
    print("GOT", got)
    assert [
        [row["t1"]["label"], row["t2"]["label"]] for row in raw_data
    ] == exp_join2_labels
    group_keys = weave.use(joined.joinObj()).to_pylist_notags()
    got = [key["sha256"] for key in group_keys]
    print("GOT", got)
    assert [key["sha256"] for key in group_keys] == exp_join2_tag_shas


def test_html_encoding_decoding(fake_wandb):
    # Familiar wandb sdk code:
    html = make_html()

    art = wandb.Artifact("test_name", "test_type")
    art.add(html, "html")

    # new helper:
    art_node = fake_wandb.mock_artifact_as_node(art)

    # Weave Query off table:
    file_node = art_node.file("media/html/349dc3aced6290aac120.html")
    contents = file.file_contents(file_node)
    result = weave.use(contents)
    assert HTML_STRING in result
