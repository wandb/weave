import moment from 'moment';

import * as Urls from '../../_external/util/urls';
import {list, maybe, typedDict} from '../../model/helpers';
import {docType} from '../../util/docs';
import {sanitizeGQLAlias} from '../../util/string';
import {makeStandardOp} from '../opKinds';
import {connectionToNodes} from './util';

const makeArtifactOp = makeStandardOp;

const artifactArgDescription = `A ${docType('artifact')}`;

const artifactArgTypes = {
  artifact: 'artifact' as const,
};

export const opArtifactId = makeArtifactOp({
  hidden: true,
  name: 'artifact-id',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifact}) => artifact.id,
});

export const opArtifactName = makeArtifactOp({
  name: 'artifact-name',
  argTypes: artifactArgTypes,
  description: `Returns the name of the ${docType('artifact')}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The name of the ${docType('artifact')}`,
  returnType: inputTypes => 'string',
  resolver: ({artifact}) => artifact.name,
});

export const opArtifactDescription = makeArtifactOp({
  hidden: true,
  name: 'artifact-description',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifact}) => artifact.description,
});

export const opArtifactAliases = makeArtifactOp({
  hidden: true,
  name: 'artifact-aliases',
  argTypes: artifactArgTypes,
  returnType: inputTypes => list('artifactAlias'),
  resolver: ({artifact}) => connectionToNodes(artifact.aliases),
});

// Hiding, We don't like the word "type" here.
export const opArtifactType = makeArtifactOp({
  hidden: true,
  name: 'artifact-type',
  argTypes: artifactArgTypes,
  description: `Returns the type of the ${docType('artifact')}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The type of the ${docType('artifact')}`,
  returnType: inputTypes => maybe('artifactType'),
  resolver: ({artifact}) => artifact.defaultArtifactType,
});

export const opArtifactVersions = makeArtifactOp({
  name: 'artifact-versions',
  argTypes: artifactArgTypes,
  description: `Returns the versions of the ${docType('artifact')}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The versions of the ${docType('artifact')}`,
  returnType: inputTypes => list('artifactVersion'),
  resolver: ({artifact}) => connectionToNodes(artifact.artifacts),
});

export const opArtifactLastMembership = makeArtifactOp({
  hidden: true,
  name: 'artifact-lastMembership',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'artifactMembership',
  resolver: ({artifact}) => connectionToNodes(artifact.lastMembership)[0],
});

export const opArtifactCreatedAt = makeArtifactOp({
  hidden: true,
  name: 'artifact-createdAt',
  argTypes: artifactArgTypes,
  description: `Returns the creation date of the ${docType('artifact')}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The creation date of the ${docType('artifact')}`,
  returnType: inputTypes => 'date',
  resolver: ({artifact}) => moment(artifact.createdAt + 'Z').toDate(),
});

export const opArtifactProject = makeArtifactOp({
  hidden: true,
  name: 'artifact-project',
  argTypes: artifactArgTypes,
  description: `Returns the ${docType('project')} of the ${docType(
    'artifact'
  )}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The ${docType('project')} of the ${docType(
    'artifact'
  )}`,
  returnType: inputTypes => 'project',
  resolver: ({artifact}) => artifact.project,
});

export const opArtifactLink = makeArtifactOp({
  name: 'artifact-link',
  argTypes: artifactArgTypes,
  description: `Returns the url for a ${docType('artifact')}`,
  argDescriptions: {artifact: artifactArgDescription},
  returnValueDescription: `The url for a ${docType('artifact')}`,
  returnType: inputTypes => 'link',
  resolver: ({artifact}) => {
    return {
      name: artifact.name,
      url: Urls.artifactCollection({
        entityName: artifact.project.entity.name,
        projectName: artifact.project.name,
        artifactTypeName: artifact.defaultArtifactType.name,
        artifactCollectionName: artifact.name,
      }),
    };
  },
});

export const opArtifactMemberships = makeArtifactOp({
  hidden: true,
  name: 'artifact-memberships',
  argTypes: artifactArgTypes,
  returnType: inputTypes => list('artifactMembership'),
  resolver: ({artifact}) => connectionToNodes(artifact.artifactMemberships),
});

export const opArtifactMembershipForAlias = makeArtifactOp({
  hidden: true,
  name: 'artifact-membershipForAlias',
  argTypes: {
    artifact: 'artifact' as const,
    aliasName: 'string' as const,
  },
  returnType: inputTypes => {
    return 'artifactMembership';
  },
  resolver: ({artifact, aliasName}) =>
    artifact[sanitizeGQLAlias(`artifactMembership_${aliasName}`)],
});

export const opArtifactIsPortfolio = makeArtifactOp({
  hidden: true,
  name: 'artifact-isPortfolio',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'boolean',
  resolver: ({artifact}) => artifact.__typename === 'ArtifactPortfolio',
});

// (Tim): Adding this op after Weave0 op-freeze - in the future we can make a
// custom tag type For now just get the tags as a list of dicts
export const opArtifactRawTags = makeArtifactOp({
  hidden: true,
  name: 'artifact-rawTags',
  argTypes: artifactArgTypes,
  returnType: inputTypes =>
    list(
      typedDict({
        id: 'string',
        name: 'string',
        tagCategoryName: 'string',
        attributes: 'string',
      })
    ),
  resolver: ({artifact}) => connectionToNodes(artifact.tags),
});
