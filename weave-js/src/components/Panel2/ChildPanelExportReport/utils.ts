import {useBranchPointFromURIString} from '../../PagePanelComponents/hooks';
import {uriFromNode, determineURISource} from '../../PagePanelComponents/util';
import {ChildPanelFullConfig} from '../ChildPanel';
import {format, getYear} from 'date-fns';

export const CREATE_NEW_REPORT_OPTION = 'Create new report';
export const DEFAULT_REPORT_OPTION = {
  id: null,
  name: CREATE_NEW_REPORT_OPTION,
  projectName: null,
};

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

export function useEntityAndProject(root_config: ChildPanelFullConfig) {
  const inputNode = root_config.input_node;
  const maybeURI = uriFromNode(inputNode);
  const branchPoint = useBranchPointFromURIString(maybeURI);
  const entityProjectName = determineURISource(maybeURI, branchPoint);

  return {
    entityName: entityProjectName?.entity ?? '',
    projectName: entityProjectName?.project ?? '',
  };
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
