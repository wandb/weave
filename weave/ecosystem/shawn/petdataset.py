import PIL
import os
import typing

import weave


class OxfordIIITPetDatasetItem(typing.TypedDict):
    id: str
    class_id: int
    species: str
    breed: str
    image: PIL.Image.Image


@weave.type()
class PetadataRenderConfig:
    pass


SPECIES = ["cat", "dog"]

CAT_BREEDS = [
    "Abyssinian",
    "Bengal",
    "Birman",
    "Bombay",
    "British_Shorthair",
    "Egyptian_Mau",
    "Maine_Coon",
    "Persian",
    "Ragdoll",
    "Russian_Blue",
    "Siamese",
    "Sphynx",
]

DOG_BREEDS = [
    "american_bulldog",
    "american_pit_bull_terrier",
    "basset_hound",
    "beagle",
    "boxer",
    "chihuahua",
    "english_cocker_spaniel",
    "english_setter",
    "german_shorthaired",
    "great_pyrenees",
    "havanese",
    "japanese_chin",
    "keeshond",
    "leonberger",
    "miniature_pinscher",
    "newfoundland",
    "pomeranian",
    "pug",
    "saint_bernard",
    "samoyed",
    "scottish_terrier",
    "shiba_inu",
    "staffordshire_bull_terrier",
    "wheaten_terrier",
    "yorkshire_terrier",
]


@weave.type()
class PetDatasetPanel(weave.Panel):
    id = "PetDatasetPanel"
    input_node: weave.Node[list[OxfordIIITPetDatasetItem]]

    @weave.op()
    def render(self) -> weave.panels.Table:
        return weave.panels.Table(
            self.input_node,
            columns=[
                lambda item: item["id"],
                lambda item: item["image"],
                lambda item: item["combined_class_id"],
                lambda item: item["species_id"],
                lambda item: item["breed_id"],
            ],
        )


@weave.op()
def petdataset(
    raw_data_path: str,
) -> list[OxfordIIITPetDatasetItem]:  # TODO: use weave path
    # Download from here: https://www.robots.ox.ac.uk/~vgg/data/pets/

    annotations_list_path = os.path.join(raw_data_path, "annotations", "list.txt")
    items: list[OxfordIIITPetDatasetItem] = []

    # For now, shuffle them so we get an interesting subset
    import random

    lines = open(annotations_list_path).read().split("\n")
    random.shuffle(lines)

    with open(annotations_list_path) as f:
        for i, line in zip(range(50), lines):
            # skip comments
            if line.startswith("#"):
                continue
            img_id, class_id, species_id, breed_id = line.strip().split(" ")
            img_path = os.path.join(raw_data_path, "images", f"{img_id}.jpg")
            img = PIL.Image.open(img_path)
            img.load()

            if species_id == "1":
                species = "cat"
                breed = CAT_BREEDS[int(breed_id) - 1]
            else:
                species = "dog"
                breed = DOG_BREEDS[int(breed_id) - 1]

            items.append(
                OxfordIIITPetDatasetItem(
                    id=img_id,
                    class_id=int(class_id),
                    species=species,
                    breed=breed,
                    image=img,
                )
            )
    return items
