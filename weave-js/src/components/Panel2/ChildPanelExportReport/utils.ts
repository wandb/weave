import {useBranchPointFromURIString} from '../../PagePanelComponents/hooks';
import {uriFromNode, determineURISource} from '../../PagePanelComponents/util';
import {ChildPanelFullConfig} from '../ChildPanel';

export const CREATE_NEW_REPORT_OPTION = 'Create new report';
export const DEFAULT_REPORT_OPTION = {
  id: null,
  name: CREATE_NEW_REPORT_OPTION,
  projectName: null,
};

export type EntityOption = Record<'value', string>;
export type ReportOption = {
  id?: string;
  name: string;
  projectName?: string;
};

export const useEntityAndProject = (config: ChildPanelFullConfig) => {
  const inputNode = config.input_node;
  const maybeURI = uriFromNode(inputNode);
  const branchPoint = useBranchPointFromURIString(maybeURI);
  const entityProjectName = determineURISource(maybeURI, branchPoint);

  return {
    entityName: entityProjectName?.entity ?? '',
    projectName: entityProjectName?.project ?? '',
  };
};
