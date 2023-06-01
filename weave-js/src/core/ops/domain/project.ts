import * as Urls from '../../_external/util/urls';
import {hash, list} from '../../model';
import {docType} from '../../util/docs';
import * as OpKinds from '../opKinds';
import {connectionToNodes} from './util';

const makeProjectOp = OpKinds.makeTaggingStandardOp;

const projectArgTypes = {
  project: 'project' as const,
};

const projectArgDescription = `A ${docType('project')}`;

export const opGetProjectTag = OpKinds.makeTagGetterOp({
  name: 'tag-project',
  tagName: 'project',
  tagType: 'project',
});

export const opProjectInternalId = makeProjectOp({
  hidden: true,
  name: 'project-internalId',
  argTypes: projectArgTypes,
  description: `Returns the internal id of the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The internal id of the ${docType('project')}`,
  returnType: inputTypes => 'string',
  resolver: ({project}) => {
    return project.id;
  },
});

export const opProjectEntity = makeProjectOp({
  hidden: true,
  name: 'project-entity',
  argTypes: projectArgTypes,
  description: `Returns the internal id of the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The internal id of the ${docType('project')}`,
  returnType: inputTypes => 'entity',
  resolver: ({project}) => {
    return project.entity;
  },
});

export const opProjectCreatedAt = makeProjectOp({
  name: 'project-createdAt',
  argTypes: projectArgTypes,
  description: `Returns the creation time of the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The creation time of the ${docType('project')}`,
  returnType: inputTypes => 'date',
  resolver: ({project}) => new Date(project.createdAt + 'Z'),
});

export const opProjectUpdatedAt = makeProjectOp({
  name: 'project-updatedAt',
  argTypes: projectArgTypes,
  description: `Returns the update time of the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The update time of the ${docType('project')}`,
  returnType: inputTypes => 'date',
  resolver: ({project}) => new Date(project.updatedAt + 'Z'),
});

export const opProjectName = makeProjectOp({
  name: 'project-name',
  argTypes: projectArgTypes,
  description: `Returns the name of the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The name of the ${docType('project')}`,
  returnType: inputTypes => 'string',
  resolver: ({project}) => project.name,
});

export const opProjectLink = makeProjectOp({
  hidden: true,
  name: 'project-link',
  argTypes: projectArgTypes,
  description: `Returns the link to the ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The link to the ${docType('project')}`,
  returnType: inputTypes => 'link',
  resolver: ({project}) => ({
    name: project.name,
    url: Urls.project({
      name: project.name,
      entityName: project.entityName,
    }),
  }),
});

// Note this doesn't do the right thing at all if we try to request more than
// one run off a single project!
export const opProjectRun = makeProjectOp({
  hidden: true,
  name: 'project-run',
  argTypes: {...projectArgTypes, runName: 'string'},
  description: `Returns the ${docType(
    'run'
  )} with the given name from a ${docType('project')}`,
  argDescriptions: {
    project: projectArgDescription,
    runName: `The name of the ${docType('run')}`,
  },
  returnValueDescription: `The ${docType(
    'run'
  )} with the given name from a ${docType('project')}`,
  returnType: inputTypes => 'run',
  resolver: ({project, runName}) => {
    const alias = `run_${hash(runName)}`;
    return project[alias];
  },
});

export const opProjectRuns = makeProjectOp({
  name: 'project-runs',
  argTypes: projectArgTypes,
  description: `Returns the ${docType('run', {
    plural: true,
  })} from a ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The ${docType('run', {
    plural: true,
  })} from a ${docType('project')}`,
  returnType: inputTypes => list('run'),
  resolver: ({project}) => connectionToNodes(project.runs),
});

// This is a version of opProjectRuns that allows us to manually
// provide a filter parameter to pass to the GQL field.  This is
// a performance stopgap, not intended for end users.  Do not unhide.
export const opProjectFilteredRuns = makeProjectOp({
  hidden: true,
  name: 'project-filteredRuns',
  argTypes: {...projectArgTypes, filter: 'string', order: 'string'},
  description: `Returns the ${docType('run', {
    plural: true,
  })} from a ${docType('project')} with a filter applied`,
  argDescriptions: {
    project: projectArgDescription,
    filter: `The filter to apply to the ${docType('run', {
      plural: true,
    })}`,
    order: `The order to return the ${docType('run', {plural: true})}`,
  },
  returnValueDescription: `The ${docType('run', {
    plural: true,
  })} from a ${docType('project')} with a filter applied`,
  returnType: inputTypes => list('run'),
  resolver: ({project, filter}) => {
    const alias = `filteredRuns_${hash(filter)}`;
    if (typeof project[alias] === 'undefined') {
      throw new Error(
        `opProjectedFilteredRuns couldn't find expected project field ${alias}`
      );
    }
    return connectionToNodes(project[alias]);
  },
});

export const opProjectArtifactType = makeProjectOp({
  name: 'project-artifactType',
  argTypes: {
    ...projectArgTypes,
    artifactType: 'string',
  },
  description: `Returns the ${docType(
    'artifactType'
  )} for a given name within a ${docType('project')}`,
  argDescriptions: {
    project: projectArgDescription,
    artifactType: `The name of the ${docType('artifactType')}`,
  },
  returnValueDescription: `The ${docType(
    'artifactType'
  )} for a given name within a ${docType('project')}`,
  returnType: inputTypes => 'artifactType',
  resolver: ({project, artifactType}) => {
    const alias = `artifactType_${hash(artifactType)}`;
    return project[alias];
  },
});

export const opProjectArtifactTypes = makeProjectOp({
  name: 'project-artifactTypes',
  argTypes: {
    ...projectArgTypes,
  },
  description: `Returns the ${docType('artifactType', {
    plural: true,
  })} for a ${docType('project')}`,
  argDescriptions: {
    project: projectArgDescription,
  },
  returnValueDescription: `The ${docType('artifactType', {
    plural: true,
  })} for a ${docType('project')}`,
  returnType: inputTypes => list('artifactType'),
  resolver: ({project}) => connectionToNodes(project.artifactTypes),
});

export const opProjectArtifact = makeProjectOp({
  name: 'project-artifact',
  argTypes: {
    ...projectArgTypes,
    artifactName: 'string',
  },
  description: `Returns the ${docType(
    'artifact'
  )} for a given name within a ${docType('project')}`,
  argDescriptions: {
    project: projectArgDescription,
    artifactName: `The name of the ${docType('artifact')}`,
  },
  returnValueDescription: `The ${docType(
    'artifact'
  )} for a given name within a ${docType('project')}`,
  returnType: inputTypes => 'artifact',
  resolver: ({project, artifactName}) => {
    const alias = `artifactCollection_${hash(artifactName)}`;
    return project[alias] ?? null;
  },
});

export const opProjectArtifactVersion = makeProjectOp({
  // hidden: true,
  name: 'project-artifactVersion',
  argTypes: {
    ...projectArgTypes,
    artifactName: 'string',
    artifactVersionAlias: 'string',
  },
  description: `Returns the ${docType(
    'artifactVersion'
  )} for a given name and version within a ${docType('project')}`,
  argDescriptions: {
    project: projectArgDescription,
    artifactName: `The name of the ${docType('artifactVersion')}`,
    artifactVersionAlias: `The version alias of the ${docType(
      'artifactVersion'
    )}`,
  },
  returnValueDescription: `The ${docType(
    'artifactVersion'
  )} for a given name and version within a ${docType('project')}`,
  returnType: inputTypes => 'artifactVersion',
  resolver: ({project, artifactName, artifactVersionAlias}) => {
    const fullName = artifactName + ':' + artifactVersionAlias;
    const alias = `artifact_${hash(fullName)}`;
    return project[alias];
  },
});

export const opProjectReports = makeProjectOp({
  hidden: true,
  name: 'project-reports',
  argTypes: projectArgTypes,
  description: `Returns the ${docType('report', {
    plural: true,
  })} for a ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The ${docType('report', {
    plural: true,
  })} for a ${docType('project')}`,
  returnType: inputTypes => list('report'),
  resolver: ({project}) => connectionToNodes(project.allViews),
});

export const opProjectArtifacts = makeProjectOp({
  hidden: true,
  name: 'project-artifacts',
  argTypes: projectArgTypes,
  description: `Returns the ${docType('artifact', {
    plural: true,
  })} for a ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The ${docType('artifact', {
    plural: true,
  })} for a ${docType('project')}`,
  returnType: inputTypes => list('artifact'),
  resolver: ({project}) => connectionToNodes(project.artifactCollections),
});

export const opProjectRunQueues = makeProjectOp({
  hidden: true,
  name: 'project-runQueues',
  argTypes: projectArgTypes,
  description: `Returns the ${docType('runQueue', {
    plural: true,
  })} for a ${docType('project')}`,
  argDescriptions: {project: projectArgDescription},
  returnValueDescription: `The ${docType('runQueue', {
    plural: true,
  })} for a ${docType('project')}`,
  returnType: inputTypes => list('runQueue'),
  resolver: ({project}) => project.runQueues,
});
