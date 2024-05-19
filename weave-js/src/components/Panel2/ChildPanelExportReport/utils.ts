import {ExcludeNullish, Unpack} from '@wandb/weave/common/types/base';
import {ID} from '@wandb/weave/common/util/id';
import {
  GetReportQuery,
  UpsertReportMutationVariables,
  ViewSource,
} from '@wandb/weave/generated/graphql';
import {format, getYear} from 'date-fns';
import {useMemo} from 'react';

import {useBranchPointFromURIString} from '../../PagePanelComponents/hooks';
import {determineURISource, uriFromNode} from '../../PagePanelComponents/util';
import {ChildPanelFullConfig} from '../ChildPanel';
import {WeavePanelSlateNode} from './computeReportSlateNode';

export const NEW_REPORT_LABEL = 'New report';
export const DEFAULT_REPORT_OPTION = {
  id: NEW_REPORT_LABEL,
  name: NEW_REPORT_LABEL,
};
export function isNewReportOption(option: ReportOption | null) {
  return option?.name === NEW_REPORT_LABEL;
}

export type EntityOption = {
  name: string;
  isTeam: boolean;
};

export type ReportOption = {
  id?: string;
  name: string;
  projectName?: string;
  updatedAt?: number;
};
export type GroupedReportOption = {
  options: ReportOption[];
};

export type ProjectOption = {
  name: string;
};

export function useEntityAndProject(rootConfig: ChildPanelFullConfig) {
  const inputNode = rootConfig.input_node;
  const maybeURI = uriFromNode(inputNode);
  const branchPoint = useBranchPointFromURIString(maybeURI);
  const entityProjectName = determineURISource(maybeURI, branchPoint);

  return useMemo(
    () => ({
      entityName: entityProjectName?.entity ?? '',
      projectName: entityProjectName?.project ?? '',
    }),
    [entityProjectName]
  );
}

/**
 *
 * This is a custom formatter for TimeAgo.
 */
type formatUpdatedAtArgs = {
  date: number;
  value: number;
  unit: string;
  suffix: string;
};

export function formatUpdatedAt({
  date,
  value,
  unit,
  suffix,
}: formatUpdatedAtArgs) {
  if (unit === 'second') {
    return `${value} sec ${suffix}`;
  }
  if (unit === 'minute') {
    return `${value} min ${suffix}`;
  }
  if (unit === 'hour') {
    return `${value} hr ${suffix}`;
  }
  if (unit === 'day' && value === 1) {
    return 'Yesterday';
  }
  if (getYear(date) !== getYear(new Date())) {
    return format(date, 'MMM dd, yy');
  }
  // Handles when unit is "week", "month"
  return format(date, 'MMM dd');
}

export type PublishedReport = ExcludeNullish<GetReportQuery['view']>;
export type ReportDraft = ExcludeNullish<
  Unpack<ExcludeNullish<PublishedReport['children']>['edges']>['node']
>;

/**
 * Returns the draft of the report authored by the specified user (if exists)
 * @param report the published report whose drafts should be checked
 * @userId ID of the user whose draft we're looking for
 */
export function getReportDraftByUser(
  report: PublishedReport,
  userId: string
): ReportDraft | undefined {
  const drafts = report.children?.edges.map(({node}) => node);
  return drafts?.find(draft => draft?.user?.id === userId) ?? undefined;
}

/**
 * Generates an empty config for a new slate report
 * @param initialBlocks (optional) - initial contents for the report body
 */
export function getEmptyReportConfig(
  initialBlocks: WeavePanelSlateNode[] = []
) {
  return {
    blocks: [...initialBlocks, {type: 'paragraph', children: [{text: ''}]}],
    discussionThreads: [],
    panelSettings: {
      xAxis: '_step',
      smoothingWeight: 0,
      smoothingType: 'exponential',
      ignoreOutliers: false,
      xAxisActive: false,
      smoothingActive: false,
      useRunsTableGroupingInPanels: true,
    },
    width: 'readable',
    version: 5, // ReportSpecVersion.SlateReport
  };
}

/**
 * Returns the variables for an UpsertReport mutation that
 * creates a brand new report.
 * @param entityName Name of the entity to add the report to
 * @param projectName Name of the project to add the report to
 * @param slateNode Node to add as initial contents of the report
 */
export function newReportVariables(
  entityName: string,
  projectName: string,
  slateNode: WeavePanelSlateNode
): UpsertReportMutationVariables {
  return {
    createdUsing: ViewSource.WeaveUi,
    description: '',
    displayName: 'Untitled Report',
    entityName,
    name: ID(12),
    projectName,
    spec: JSON.stringify(getEmptyReportConfig([slateNode])),
    type: 'runs/draft',
  };
}

/**
 * Returns the variables for an UpsertReport mutation that
 * updates an existing report draft.
 * @param draft The report draft to be edited
 * @param slateNode The node to add to the draft
 */
export function editDraftVariables(
  draft: ReportDraft,
  slateNode: WeavePanelSlateNode
): UpsertReportMutationVariables {
  const spec = JSON.parse(draft.spec);
  spec.blocks.push(slateNode);
  return {
    id: draft.id,
    spec: JSON.stringify(spec),
  };
}

/**
 * Returns the variables for an UpsertReport mutation that
 * creates a new draft from a published report.
 * @param report The published report to start a new draft for
 * @param slateNode The node to add to the new report draft
 */
export function newDraftVariables(
  entityName: string,
  projectName: string,
  report: PublishedReport,
  slateNode: WeavePanelSlateNode
): UpsertReportMutationVariables {
  const spec = JSON.parse(report.spec);
  spec.blocks.push(slateNode);
  return {
    coverUrl: report.coverUrl,
    description: report.description,
    displayName: report.displayName,
    entityName,
    name: ID(12),
    parentId: report.id,
    previewUrl: report.previewUrl,
    projectName,
    spec: JSON.stringify(spec),
    type: 'runs/draft',
  };
}
