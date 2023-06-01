import type {Type} from '../../model';
import {
  BASIC_MEDIA_TYPES,
  constNode,
  constString,
  getActualNamedTagFromValue,
  mappableNullable,
  mappableNullableTaggable,
  mappableNullableTaggableValAsync,
  mappableNullableVal,
  maybe,
  nullableOneOrMany,
  union,
  withFileTag,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {opArtifactVersionFile} from './artifactVersion';

// Hide for now, its showing up at the top of the suggestion list
// TODO: this should make use of opKinds TagGetterOp. We'll need
// TagGetterOp to accept a callback that can be used to apply a
// function to the returned tag.
export const opAssetArtifactVersion = makeOp({
  hidden: true,
  name: 'asset-artifactVersion',
  argTypes: {
    asset: nullableOneOrMany(union([withFileTag('any', {type: 'file'})])),
  },
  description: `Returns the ${docType('artifactVersion')} of the asset`,
  argDescriptions: {
    asset: 'The asset',
  },
  returnValueDescription: `The ${docType('artifactVersion')} of the asset`,
  returnType: inputs =>
    mappableNullable(inputs.asset.type, t => maybe('artifactVersion')),
  resolver: inputs => {
    const ret = mappableNullableVal(inputs.asset, asset => {
      const tag = getActualNamedTagFromValue(asset, 'file');
      const artifactId = tag?.file?.artifact?.id;
      if (artifactId == null) {
        console.warn(
          'opAssetArtifactVersion: unable to locate `artifactId` for asset with file tag',
          {
            asset,
            fileTag: tag,
          }
        );
        return null;
      }
      return {id: artifactId};
    });
    return ret;
  },
});

// Keeping this restricted to types which are guaranteed to have a path
export const mediaAssetArgTypes = {
  asset: nullableOneOrMany(union(BASIC_MEDIA_TYPES)),
};

export const opAssetFile = makeOp({
  name: 'asset-file',
  argTypes: mediaAssetArgTypes,
  description: `Returns the ${docType('file')} of the asset`,
  argDescriptions: {
    asset: 'The asset',
  },
  returnValueDescription: `The ${docType('file')} of the asset`,
  returnType: inputs =>
    mappableNullableTaggable(inputs.asset.type, t => {
      return {type: 'file'};
    }),
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    const assetNode = constNode<Type>(
      forwardOp.outputNode.node.type,
      inputs.asset
    );
    const files = await mappableNullableTaggableValAsync(
      inputs.asset,
      async asset => {
        return (
          await engine().executeNodes(
            [
              opArtifactVersionFile({
                artifactVersion: opAssetArtifactVersion({asset: assetNode}),
                path: constString(asset.path),
              }),
            ],
            false
          )
        )[0];
      }
    );
    return files;
  },
});
