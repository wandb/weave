import {useMutation, useQuery} from '@apollo/client';
import * as Urls from '@wandb/weave/core/_external/util/urls';
import {opRootViewer} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React, {useState} from 'react';
import _ from 'lodash';

import {Alert} from '../../Alert.styles';
import {Button} from '../../Button';
import {ChildPanelFullConfig} from '../ChildPanel';
import {Tailwind} from '../../Tailwind';
import {ErrorAlerts} from './ErrorAlerts';
import {useCloseDrawer, useSelectedPath} from '../PanelInteractContext';
import {ReportSelection} from './ReportSelection';
import {computeReportSlateNode} from './computeReportSlateNode';
import {GET_REPORT, UPSERT_REPORT} from './graphql';
import {
  EntityOption,
  ProjectOption,
  ReportOption,
  isNewReportOption,
} from './utils';

type ChildPanelExportReportProps = {
  /**
   * "root" config of the board, which points to the artifact that contains
   * the "full" config with actual details about all the sub-panels within
   */
  rootConfig: ChildPanelFullConfig;
};

export const ChildPanelExportReport = ({
  rootConfig,
}: ChildPanelExportReportProps) => {
  const {result: viewer} = useNodeValue(opRootViewer({}));
  const {result: fullConfig} = useNodeValue(rootConfig.input_node);
  const selectedPath = useSelectedPath();
  const closeDrawer = useCloseDrawer();

  const [selectedEntity, setSelectedEntity] = useState<EntityOption | null>(
    null
  );
  const [selectedReport, setSelectedReport] = useState<ReportOption | null>(
    null
  );
  const [selectedProject, setSelectedProject] = useState<ProjectOption | null>(
    null
  );

  const isNewReportSelected = isNewReportOption(selectedReport);

  const [upsertReport, upsertReportResult] = useMutation(UPSERT_REPORT);
  const reportQueryResult = useQuery(GET_REPORT, {
    variables: {id: selectedReport?.id ?? ''},
    skip: !selectedReport || isNewReportOption(selectedReport),
  });

  const isErrorDisplayed = reportQueryResult.error || upsertReportResult.error;
  const isAddPanelDisabled =
    !selectedEntity ||
    !selectedReport ||
    !selectedProject ||
    reportQueryResult.loading ||
    reportQueryResult.error != null ||
    upsertReportResult.loading;

  const onAddPanel = async () => {
    if (isAddPanelDisabled) {
      return;
    }

    const slateNode = computeReportSlateNode(fullConfig, selectedPath);
    const entityName = selectedEntity.name;
    const projectName = selectedProject.name;
    let upsertBody;

    if (isNewReportSelected) {
      // https://wandb.atlassian.net/browse/WB-15495
      alert('TODO: handle new report option');
      return;
    } else {
      const publishedReport = reportQueryResult.data?.view;
      const drafts = publishedReport?.children?.edges.map(({node}) => node);
      const viewerDraft = drafts?.find(draft => draft?.user?.id === viewer.id);
      if (viewerDraft) {
        const spec = JSON.parse(viewerDraft.spec);
        spec.blocks.push(slateNode);
        upsertBody = {
          id: viewerDraft.id,
          spec: JSON.stringify(spec),
        };
      } else {
        // https://wandb.atlassian.net/browse/WB-15494
        alert('TODO: handle report without existing draft');
        return;
      }
    }

    const result = await upsertReport({variables: upsertBody});
    const upsertedDraft = result.data?.upsertView?.view!;
    const reportDraftPath = Urls.reportEdit({
      entityName,
      projectName,
      reportID: upsertedDraft.id,
      reportName: upsertedDraft.displayName ?? '',
    });

    // Should set hostname per env (e.g. dev, local, saas), presumably with urlPrefixed?
    // eslint-disable-next-line wandb/no-unprefixed-urls
    window.open(`https://wandb.ai/${reportDraftPath}`, '_blank');
    closeDrawer();
  };

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-moon-250 px-16 py-12">
          <h2 className="text-lg font-semibold">
            Add {_.last(selectedPath)} to report
          </h2>
          <Button icon="close" variant="ghost" onClick={closeDrawer} />
        </div>
        <div className="flex-1 gap-8 p-16">
          <Alert severity="warning">
            <p>
              <b>🚧 Work in progress!</b> This feature is under development
              behind an internal-only feature flag.
            </p>
          </Alert>
          <ReportSelection
            rootConfig={rootConfig}
            selectedEntity={selectedEntity}
            selectedReport={selectedReport}
            selectedProject={selectedProject}
            setSelectedEntity={setSelectedEntity}
            setSelectedReport={setSelectedReport}
            setSelectedProject={setSelectedProject}
            onChange={upsertReportResult.reset}
          />
          {!isErrorDisplayed && (
            <p className="mt-16 text-moon-500">
              Future changes to the board will not affect exported panels inside
              reports.
            </p>
          )}
          {reportQueryResult.error && (
            <ErrorAlerts.ReportQuery error={reportQueryResult.error} />
          )}
          {upsertReportResult.error && (
            <ErrorAlerts.UpsertReport error={upsertReportResult.error} />
          )}
        </div>
        <div className="border-t border-moon-250 px-16 py-20">
          <Button
            icon="add-new"
            className="w-full"
            disabled={isAddPanelDisabled}
            onClick={onAddPanel}>
            Add panel
          </Button>
        </div>
      </div>
    </Tailwind>
  );
};
