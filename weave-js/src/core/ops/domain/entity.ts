import {list, maybe} from '../../model/helpers';
import {docType} from '../../util/docs';
import {makeTaggingStandardOp} from '../opKinds';
import {connectionToNodes} from './util';

const makeEntityOp = makeTaggingStandardOp;

const entityArgTypes = {
  entity: 'entity' as const,
};

const entityArgDescription = `A ${docType('entity')}`;

export const opEntityInternalId = makeEntityOp({
  hidden: true,
  name: 'entity-internalId',
  argTypes: entityArgTypes,
  description: `Returns the internalId of the ${docType('entity')}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The internalId of the ${docType('entity')}`,
  returnType: inputTypes => 'string',
  resolver: ({entity}) => {
    return entity.id;
  },
});

export const opEntityName = makeEntityOp({
  name: 'entity-name',
  argTypes: entityArgTypes,
  description: `Returns the name of the ${docType('entity')}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The name of the ${docType('entity')}`,
  returnType: inputTypes => 'string',
  resolver: ({entity}) => {
    return entity.name;
  },
});

export const opEntityIsTeam = makeEntityOp({
  hidden: true,
  name: 'entity-isTeam',
  argTypes: entityArgTypes,
  returnType: inputTypes => 'boolean',
  resolver: ({entity}) => {
    return entity.isTeam;
  },
});

export const opEntityLink = makeEntityOp({
  name: 'entity-link',
  argTypes: entityArgTypes,
  description: `Returns the link of the ${docType('entity')}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The link of the ${docType('entity')}`,
  returnType: inputTypes => 'link',
  resolver: ({entity}) => {
    return {
      name: entity.name,
      url: `/${entity.name}`,
    };
  },
});

export const opEntityProjects = makeEntityOp({
  hidden: true,
  name: 'entity-projects',
  argTypes: entityArgTypes,
  description: `Returns the ${
    (docType('project'), {plural: true})
  } of the ${docType('entity')}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The ${
    (docType('project'), {plural: true})
  } of the ${docType('entity')}`,
  returnType: inputTypes => list('project'),
  resolver: ({entity}) => connectionToNodes(entity.projects),
});

export const opEntityReports = makeEntityOp({
  hidden: true,
  name: 'entity-reports',
  argTypes: entityArgTypes,
  description: `Returns the ${
    (docType('report'), {plural: true})
  } of the ${docType('entity')}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The ${
    (docType('report'), {plural: true})
  } of the ${docType('entity')}`,
  returnType: inputTypes => list('report'),
  resolver: ({entity}) => connectionToNodes(entity.views),
});

export const opEntityArtifactPortfolios = makeEntityOp({
  hidden: true,
  name: 'entity-portfolios',
  argTypes: entityArgTypes,
  description: `Returns the ${docType('artifact')} portfolios of the ${docType(
    'entity'
  )}`,
  argDescriptions: {
    entity: entityArgDescription,
  },
  returnValueDescription: `The ${docType(
    'artifact'
  )} portfolios of the ${docType('entity')}`,
  returnType: inputTypes => list('artifact'),
  resolver: ({entity}) => connectionToNodes(entity?.entityPortfolios),
});

export const opEntityOrg = makeEntityOp({
  hidden: true,
  name: 'entity-org',
  argTypes: entityArgTypes,
  returnType: inputTypes => maybe('org'),
  resolver: ({entity}) => entity.organization,
});

export const opEntityArtifactTTLDurationSeconds = makeEntityOp({
  hidden: true,
  name: 'entity-artifactTTLDurationSeconds',
  argTypes: entityArgTypes,
  returnType: inputTypes => 'number',
  resolver: ({entity}) => {
    return entity.artifactTTLDurationSeconds;
  },
});
