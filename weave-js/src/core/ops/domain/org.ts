import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {makeTaggingStandardOp} from '../opKinds';
import {connectionToNodes} from './util';

const orgArgDescription = `A ${docType('org')}`;

const makeOrgOp = makeTaggingStandardOp;

export const opOrgMembers = makeOp({
  hidden: true,
  name: 'org-members',
  argTypes: {org: 'org'},
  description: `Returns the ${docType('user', {
    plural: true,
  })} belonging of an ${docType('org')}`,
  argDescriptions: {org: orgArgDescription},
  returnValueDescription: `The ${docType('user', {
    plural: true,
  })} belonging of the ${docType('org')}`,
  returnType: {type: 'list', objectType: 'user'},
  resolver: inputs => {
    const {org} = inputs;
    return org.members.map((e: any) => e.user);
  },
});

// FIXME(np): Not safe for large orgs
// ordering ops over runs table are way too expensive
// export const opOrgRuns = Graph.makeOp({
//   hidden: true,
//   name: 'org-runs',
//   argTypes: {org: 'org'},
//   returnType: {type: 'list', objectType: 'run'},
//   resolver: inputs => {
//     const {org} = inputs;
//     return org.runs.edges.map((e: any) => e.node);
//   },
// });

export const opOrgReports = makeOp({
  hidden: true,
  name: 'org-reports',
  argTypes: {org: 'org'},
  description: `Returns the ${docType('report', {
    plural: true,
  })} of an ${docType('org')}`,
  argDescriptions: {org: orgArgDescription},
  returnValueDescription: `The ${docType('report', {
    plural: true,
  })} of the ${docType('org')}`,
  returnType: {type: 'list', objectType: 'report'},
  resolver: inputs => {
    const {org} = inputs;
    return connectionToNodes(org.views).filter((e: any) => e.type === 'runs');
  },
});

export const opOrgProjects = makeOp({
  hidden: true,
  name: 'org-projects',
  argTypes: {org: 'org'},
  description: `Returns the ${docType('project', {
    plural: true,
  })} of an ${docType('org')}`,
  argDescriptions: {org: orgArgDescription},
  returnValueDescription: `The ${docType('project', {
    plural: true,
  })} of the ${docType('org')}`,
  returnType: {type: 'list', objectType: 'project'},
  resolver: inputs => {
    const {org} = inputs;
    return connectionToNodes(org.projects);
  },
});

export const opOrgArtifacts = makeOp({
  hidden: true,
  name: 'org-artifacts',
  argTypes: {org: 'org'},
  description: `Returns the ${docType('artifact', {
    plural: true,
  })} of an ${docType('org')}`,
  argDescriptions: {org: orgArgDescription},
  returnValueDescription: `The ${docType('artifact', {
    plural: true,
  })} of the ${docType('org')}`,
  returnType: {type: 'list', objectType: 'artifact'},
  resolver: inputs => {
    const {org} = inputs;
    return connectionToNodes(org.artifactCollections);
  },
});

export const opOrgName = makeOrgOp({
  hidden: true,
  name: 'org-name',
  argTypes: {org: 'org' as const},
  returnType: it => 'string',
  resolver: ({org}: any) => org.name,
});

export const opOrgTeams = makeOrgOp({
  hidden: true,
  name: 'org-teams',
  argTypes: {org: 'org' as const},
  returnType: it => ({type: 'list' as const, objectType: 'entity' as const}),
  resolver: ({org}: any) => org.teams,
});
