# Weave Reference Format Specification

A weave reference ("ref") has the following 2 formats:

1. The W&B Artifact: `wandb-artifact:///{ENTITY}/{PROJECT}/{ARTIFACT_NAME}:{ALIAS}[/{FILE_PATH}[#REF_EXTRA]]`
   - Yes, the 3 forward slashes are correct.
2. The Local Artifact `local-artifact:///{ARTIFACT_NAME}:{ALIAS}[/{FILE_PATH}[#REF_EXTRA]]`
   - A known problem with local artifacts is that it is possible to have name collisions with artifacts of the same name, sourced from 2 different projects.

Path Component Details:

We will define the "CommonCharset" as alphanumeric and underscore `_` and dash `-`

- `ENTITY`: limited to CommonCharset
- `PROJECT`: limited to CommonCharset
- `ARTIFACT_NAME`: limited to CommonCharset
- `ALIAS`: can take 1 of 3 forms:
  - "alias": limited to CommonCharset, for example `latest`
  - "version": `v#` where `#` is an integer value
  - "digest": a deterministic hex digest of the contents
  - "versionHash": a hex digest combining the "digest" with the prior version's digest in the sequence.
- `FILE_PATH`: (optional) a list of forward slash `/` separated `FILE_PATH_PART`s. Each `FILE_PATH_PART` is limited to CommonCharset and dot `.`
- `REF_EXTRA`: (optional, only allowed if `FILE_PATH` is present) a list of forward slash `/` separated `REF_EXTRA_TUPLE`s. A `REF_EXTRA_TUPLE` has the format of `{REF_EXTRA_EDGE_TYPE}/{REF_EXTRA_PART}`. Where `REF_EXTRA_EDGE_TYPE` is one of: `ndx`, `key`, `atr`, `col`, `row`, `id`. A `REF_EXTRA_PART` is limited to CommonCharset.
  - **Important:** the `REF_EXTRA_EDGE_TYPE` of `id` is not yet implemented

When interpreting a reference, we follow the following rules:

1. Lookup the artifact itself using everything up to, but excluding the `FILE_PATH`. If no `FILE_PATH` exists, then the reference is pointing to an artifact and we halt.
2. If `FILE_PATH` exists, then we fetch the file located at such path. There are two cases:

   1. `FILE_PATH` exactly matches a member file of the artifact. In this case, the ref is pointing to the specific file and we halt.
   2. `FILE_PATH` is not contained in the artifact, but rather `FILE_PATH.type.json` is contained in the artifact. In this case, the ref is pointing to a "weave object". The Weave engine reads the `FILE_PATH.type.json` file to determine the type of the object. Reconstruction/deserialization of the object will often require reading 1 or more peer files - the rules of which are up to the type's implementation. By far the most common case here is when `FILE_PATH = "obj"`. Where we have `obj.type.json` at the root of the artifact, then a peer file, for example `obj.object.json` containing the data payload itself. Note: the peer file needn't be called `obj.object.json` - this is up to the object type to determine. **Importantly:** this is the case where the ref is pointing to a "weave object" and the file system is not important to the user. If no `REF_EXTRA` exists, we halt.

3. If a `REF_EXTRA` exists (and by definition our `FILE_PATH` points to a weave object), then the `REF_EXTRA` tells us how to traverse the object itself to extract a nested data property. For example, you might have a class called `Model` with an attribute `prompt`. If the ref wants to point to the prompt field itself, the `REF_EXTRA` would be `attr/prompt`. As mentioned above, there are a number of `REF_EXTRA_EDGE_TYPE`s that allow the ref to point deep into the object. This is useful for things like datasets where you might have an class called `Dataset` that has a property `rows` which is a list of dictionaries. At this point, we return the final data. The specific rules for `REF_EXTRA_EDGE_TYPE` are as follows:
   - If the current object is a Table (ArrowWeaveList), then:
     - `ndx/{INDEX}` - get the row at index `INDEX`
     - `col/{COLUMN_NAME}` - get the column called `COLUMN_NAME`
     - `id/{ID}` - get the row at id `ID`
   - If the current object is a Dict, then:
     - `key/{KEY}` - get the value at key `KEY`
   - If the current object is a Object, then:
     - `atr/{ATTRIBUTE}` - get the value at attribute `ATTRIBUTE`
   - If the current object is a List, then:
     - `ndx/{INDEX}` - get the item at position `INDEX`

So putting this all together, the following ref (`wandb-artifact:///example_entity/example_project/example_artifact:abc123/obj#attr/rows/index/10/key/input`) should be interpreted as follows:

- Fetch the artifact corresponding to `example_entity/example_project/example_artifact:abc123` from W&B.
- Determine that `obj` is not a specific entry but rather a "weave object"
- Get the `rows` property from the object (this could be a list or a table in this case)
- Get the row at index `10`. (this is a dictionary)
- Get the value located at the `input` key.

Note: a careful reader will notice that the same piece of data might have multiple valid refs pointing to it. Consider the following case:

1. `wandb-artifact:///example_entity/example_project/example_artifact:abc123/obj#attr/rows/index/10/key/input`
2. `wandb-artifact:///example_entity/example_project/example_artifact:abc123/rows/0#index/10/key/input`

Both of these refs will return the same exact data (assuming that the `obj` object's `rows` property is a pointer to the `rows/0` entry.). While this is perfectly fine and valid, it has a problem. Case 2 breaks the relationship as we no longer know that the data was derived from traversing into the dataset itself. If you are given reference 2, then you have no way of knowing that it is actually a descendant member of `wandb-artifact:///example_entity/example_project/example_artifact:abc123/obj` (other than maybe by convention). Reference 2 is a biproduct of the serialization format, not the logical "thing" the user is using. Therefore, when constructing refs, we always prefer case 1. However, an important exception to this rule is if during the object extra traversal, we "jump" to completely new artifact, then we restart the ref there. This allows us to preserve the name of the object.

**Further idea:** We should probably add a `?hash=CONTENT_HASH` at the end of refs - this would allow us to know if two entries in the same dataset are actually the same content. We can't purely rely on the artifact hash for uniqueness since the ref could be pointing to a deep member of the artifact.
