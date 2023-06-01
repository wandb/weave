import {list} from '../../model';
import {docType} from '../../util/docs';
import {makeStandardOp} from '../opKinds';
import {connectionToNodes} from './util';

const makeArtifactTypeOp = makeStandardOp;

const artifactTypeArgTypes = {
  artifactType: 'artifactType' as const,
};
const artifactTypeArgDescription = `A ${docType('artifactType')}`;

export const opArtifactTypeName = makeArtifactTypeOp({
  name: 'artifactType-name',
  argTypes: artifactTypeArgTypes,
  description: `Returns the name of the ${docType('artifactType')}`,
  argDescriptions: {artifactType: artifactTypeArgDescription},
  returnValueDescription: `The name of the ${docType('artifactType')}`,
  returnType: inputTypes => 'string',
  resolver: ({artifactType}) => artifactType.name,
});

export const opArtifactTypeArtifacts = makeArtifactTypeOp({
  name: 'artifactType-artifacts',
  argTypes: artifactTypeArgTypes,
  description: `Returns the ${docType('artifact', {
    plural: true,
  })} of the ${docType('artifactType')}`,
  argDescriptions: {artifactType: artifactTypeArgDescription},
  returnValueDescription: `The ${docType('artifact', {
    plural: true,
  })} of the ${docType('artifactType')}`,
  returnType: inputTypes => list('artifact'),
  resolver: ({artifactType}) =>
    connectionToNodes(artifactType.artifactCollections),
});

export const opArtifactTypeSequences = makeArtifactTypeOp({
  hidden: true,
  name: 'artifactType-sequences',
  argTypes: artifactTypeArgTypes,
  returnType: inputTypes => list('artifact'),
  resolver: ({artifactType}) =>
    connectionToNodes(artifactType.artifactSequences),
});

export const opArtifactTypePortfolios = makeArtifactTypeOp({
  hidden: true,
  name: 'artifactType-portfolios',
  argTypes: artifactTypeArgTypes,
  returnType: inputTypes => list('artifact'),
  resolver: ({artifactType}) =>
    connectionToNodes(artifactType.artifactPortfolios),
});

export const opArtifactTypeArtifactVersions = makeArtifactTypeOp({
  name: 'artifactType-artifactVersions',
  argTypes: artifactTypeArgTypes,
  description: `Returns the ${docType('artifactVersion', {
    plural: true,
  })} of all ${docType('artifact', {
    plural: true,
  })} of the ${docType('artifactType')}`,
  argDescriptions: {artifactType: artifactTypeArgDescription},
  returnValueDescription: `The ${docType('artifactVersion', {
    plural: true,
  })} of all ${docType('artifact', {
    plural: true,
  })} of the ${docType('artifactType')}`,
  returnType: inputTypes => list('artifactVersion'),
  resolver: ({artifactType}) =>
    connectionToNodes(artifactType.artifactCollections).flatMap((ac: any) =>
      connectionToNodes(ac.artifacts)
    ),
});
