import * as Urls from '../../_external/util/urls';
import type {OpInputNodes, OpResolverInputTypes, Type} from '../../model';
import {
  list,
  mappableNullableTaggable,
  mappableNullableTaggableVal,
  maybe,
  oneOrMany,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {connectionToNodes} from './util';

const reportArgTypes = {
  report: maybe(oneOrMany(maybe('report'))),
};

const reportArgDescription = `A ${docType('report')}`;

const makeReportReturnType =
  (returnType: Type) => (inputs: OpInputNodes<typeof reportArgTypes>) =>
    mappableNullableTaggable(inputs.report.type, t => returnType);

const makeReportResolver =
  (applyFn: (report: any) => any) =>
  (inputs: OpResolverInputTypes<typeof reportArgTypes>) =>
    mappableNullableTaggableVal(inputs.report, v => applyFn(v));

export const opReportInternalId = makeOp({
  hidden: true,
  name: 'report-internalId',
  argTypes: reportArgTypes,
  description: `Returns the internalId of the ${docType('report')}`,
  argDescriptions: {
    entity: reportArgDescription,
  },
  returnValueDescription: `The internalId of the ${docType('report')}`,
  returnType: makeReportReturnType('string'),
  resolver: makeReportResolver(report => report.id),
});

export const opReportName = makeOp({
  hidden: true,
  name: 'report-name',
  argTypes: reportArgTypes,
  description: `Returns the name of the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The name of the ${docType('report')}`,
  returnType: makeReportReturnType('string'),
  resolver: makeReportResolver(report => report.displayName),
});

export const opReportLink = makeOp({
  hidden: true,
  name: 'report-link',
  argTypes: reportArgTypes,
  description: `Returns the link to the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The link to the ${docType('report')}`,
  returnType: makeReportReturnType('link'),
  resolver: makeReportResolver(report => ({
    name: report.displayName,
    url: Urls.reportView({
      entityName: report.project.entityName,
      projectName: report.project.name,
      reportID: report.id,
      reportName: report.displayName,
    }),
  })),
});

export const opReportDescription = makeOp({
  hidden: true,
  name: 'report-description',
  argTypes: reportArgTypes,
  description: `Returns the description of the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The description of the ${docType('report')}`,
  returnType: makeReportReturnType('string'),
  resolver: makeReportResolver(report => report.description),
});

export const opReportCreatedAt = makeOp({
  hidden: true,
  name: 'report-createdAt',
  argTypes: reportArgTypes,
  description: `Returns the creation time of the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The creation time of the ${docType('report')}`,
  returnType: makeReportReturnType('date'),
  resolver: makeReportResolver(report => new Date(report.createdAt + 'Z')),
});

export const opReportUpdatedAt = makeOp({
  hidden: true,
  name: 'report-updatedAt',
  argTypes: reportArgTypes,
  description: `Returns the updated time of the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The updated time of the ${docType('report')}`,
  returnType: makeReportReturnType('date'),
  resolver: makeReportResolver(report => new Date(report.createdAt + 'Z')),
});

export const opReportProject = makeOp({
  hidden: true,
  name: 'report-project',
  argTypes: reportArgTypes,
  description: `Returns the ${docType('project')} of the ${docType('report')}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The ${docType('project')} of the ${docType(
    'report'
  )}`,
  returnType: makeReportReturnType('project'),
  resolver: makeReportResolver(report => report.project),
});

export const opReportCreator = makeOp({
  hidden: true,
  name: 'report-creator',
  argTypes: reportArgTypes,
  description: `Returns the ${docType('user')} who created the ${docType(
    'report'
  )}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The ${docType('user')} who created the ${docType(
    'report'
  )}`,
  returnType: makeReportReturnType('user'),
  resolver: makeReportResolver(report => report.user),
});

export const opReportViewCount = makeOp({
  hidden: true,
  name: 'report-viewcount',
  argTypes: reportArgTypes,
  description: `Returns the number of times the ${docType(
    'report'
  )} has been viewed`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The number of times the ${docType(
    'report'
  )} has been viewed`,
  returnType: makeReportReturnType('number'),
  resolver: makeReportResolver(report => report.viewCount),
});

export const opReportStargazers = makeOp({
  hidden: true,
  name: 'report-stargazers',
  argTypes: reportArgTypes,
  description: `Returns the number of users who starred the ${docType(
    'report'
  )}`,
  argDescriptions: {
    report: reportArgDescription,
  },
  returnValueDescription: `The number of users who starred the ${docType(
    'report'
  )}`,
  returnType: makeReportReturnType(list('user')),
  resolver: makeReportResolver(report => connectionToNodes(report.stargazers)),
});
