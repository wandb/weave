import {useLazyQuery, useMutation} from '@apollo/client';
import {coreAppUrl} from '@wandb/weave/config';
import {opRootViewer} from '@wandb/weave/core';
import * as Urls from '@wandb/weave/core/_external/util/urls';
import {UpsertReportMutationVariables} from '@wandb/weave/generated/graphql';
import {useNodeValue, useNodeValueExecutor} from '@wandb/weave/react';
import classNames from 'classnames';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {Button} from '../../Button';
import {Tailwind} from '../../Tailwind';
import {ChildPanelFullConfig} from '../ChildPanel';
import {useCloseDrawer, useSelectedPath} from '../PanelInteractContext';
import {isInsideMain} from '../panelTree';
import {AddPanelErrorAlert} from './AddPanelErrorAlert';
import {computeReportSlateNode} from './computeReportSlateNode';
import {DELETE_REPORT_DRAFT, GET_REPORT, UPSERT_REPORT} from './graphql';
import {ReportDraftDialog} from './ReportDraftDialog';
import {ReportSelection} from './ReportSelection';
import {
  editDraftVariables,
  EntityOption,
  getReportDraftByUser,
  isNewReportOption,
  newDraftVariables,
  newReportVariables,
  ProjectOption,
  ReportOption,
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
  const executor = useNodeValueExecutor();
  const selectedPath = useSelectedPath();
  const closeDrawer = useCloseDrawer();

  // Export is only allowed for panels *inside* main (excluding main itself)
  useEffect(() => {
    if (!isInsideMain(selectedPath)) {
      closeDrawer();
    }
  }, [selectedPath, closeDrawer]);

  // If selected path changes while the drawer is open, highlight the
  // new panel name to alert the user that the target panel changed.
  const panelName = useMemo(() => _.last(selectedPath), [selectedPath]);
  const [isPanelNameHighlighted, setIsPanelNameHighlighted] = useState<
    null | boolean
  >(null); // initial `null` lets us skip highlight when drawer is first opened
  useEffect(() => {
    setIsPanelNameHighlighted(prev => (prev === null ? false : true));
    const timeout = setTimeout(() => setIsPanelNameHighlighted(false), 1500);
    return () => clearTimeout(timeout);
  }, [selectedPath]);

  const [selectedEntity, setSelectedEntity] = useState<EntityOption | null>(
    null
  );
  const [selectedReport, setSelectedReport] = useState<ReportOption | null>(
    null
  );
  const [selectedProject, setSelectedProject] = useState<ProjectOption | null>(
    null
  );

  const [getReport, {data: reportQueryData}] = useLazyQuery(GET_REPORT);
  const [upsertReport] = useMutation(UPSERT_REPORT);
  const [deleteReportDraft] = useMutation(DELETE_REPORT_DRAFT);
  const [isAddingPanel, setIsAddingPanel] = useState(false);
  const [isDraftDialogOpen, setIsDraftDialogOpen] = useState(false);
  const [error, setError] = useState<any>(null);

  const getSlateNode = useCallback(async () => {
    const fullConfig = await executor(rootConfig.input_node);
    const slateNode = computeReportSlateNode(fullConfig, selectedPath);
    const {documentId} = slateNode.config.panelConfig.config;
    return {slateNode, documentId};
  }, [executor, rootConfig.input_node, selectedPath]);

  const publishedReport = reportQueryData?.view;
  const activeReportDraft = useMemo(
    () =>
      publishedReport && viewer
        ? getReportDraftByUser(publishedReport, viewer.id)
        : undefined,
    [publishedReport, viewer]
  );

  const isNewReportSelected = isNewReportOption(selectedReport);
  const hasRequiredData =
    selectedEntity != null && selectedReport != null && selectedProject != null;
  const hasActiveDraft = publishedReport != null && activeReportDraft != null;
  const isAddPanelDisabled = !hasRequiredData || isAddingPanel;

  const handleError = (err: any) => {
    console.error(err);
    setError(err);
    setIsAddingPanel(false);
  };

  const submit = async (
    variables: UpsertReportMutationVariables,
    documentId: string
  ) => {
    if (!hasRequiredData) {
      return;
    }
    const result = await upsertReport({variables});
    const upsertedDraft = result.data?.upsertView?.view!;
    const reportDraftPath = Urls.reportEdit(
      {
        entityName: selectedEntity.name,
        projectName: selectedProject.name,
        reportID: upsertedDraft.id,
        reportName: upsertedDraft.displayName ?? '',
      },
      `#${documentId}`
    );
    // eslint-disable-next-line wandb/no-unprefixed-urls
    window.open(coreAppUrl(reportDraftPath), '_blank');
    setIsAddingPanel(false);
    closeDrawer();
  };

  const onAddPanel = async () => {
    if (isAddPanelDisabled) {
      return;
    }
    try {
      setIsAddingPanel(true);
      const {slateNode, documentId} = await getSlateNode();
      if (isNewReportSelected) {
        return submit(
          newReportVariables(
            selectedEntity.name,
            selectedProject.name,
            slateNode
          ),
          documentId
        );
      }
      const {data} = await getReport({
        variables: {id: selectedReport.id!},
        fetchPolicy: 'no-cache',
      });
      const report = data?.view;
      if (!report) {
        throw new Error('Report not found');
      }
      const draft = getReportDraftByUser(report, viewer.id);
      if (draft) {
        return setIsDraftDialogOpen(true);
      } else {
        return submit(
          newDraftVariables(
            selectedEntity.name,
            selectedProject.name,
            report,
            slateNode
          ),
          documentId
        );
      }
    } catch (err) {
      handleError(err);
    }
  };

  const onContinueDraft = async () => {
    if (!hasActiveDraft) {
      return;
    }
    try {
      const {slateNode, documentId} = await getSlateNode();
      await submit(
        editDraftVariables(activeReportDraft, slateNode),
        documentId
      );
    } catch (err) {
      handleError(err);
    }
  };

  const onDiscardDraft = async () => {
    if (!hasActiveDraft || !hasRequiredData) {
      return;
    }
    try {
      await deleteReportDraft({
        variables: {id: activeReportDraft.id},
      });
      const {slateNode, documentId} = await getSlateNode();
      await submit(
        newDraftVariables(
          selectedEntity.name,
          selectedProject.name,
          publishedReport,
          slateNode
        ),
        documentId
      );
    } catch (err) {
      handleError(err);
    }
  };

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-moon-250 px-16 py-12">
          <h2 className="text-lg font-semibold">
            Add{' '}
            <span
              className={classNames('transition', {
                'bg-gold-300/[0.5]': isPanelNameHighlighted,
              })}>
              {panelName}
            </span>{' '}
            to report
          </h2>
          <Button icon="close" variant="ghost" onClick={closeDrawer} />
        </div>
        <div className="flex-1 gap-8 p-16">
          <ReportSelection
            rootConfig={rootConfig}
            selectedEntity={selectedEntity}
            selectedReport={selectedReport}
            selectedProject={selectedProject}
            setSelectedEntity={setSelectedEntity}
            setSelectedReport={setSelectedReport}
            setSelectedProject={setSelectedProject}
            onChange={() => setError(null)}
          />
          {!error ? (
            <p className="mt-16 text-moon-500">
              Future changes to the board will not affect exported panels inside
              reports.
            </p>
          ) : (
            <AddPanelErrorAlert
              error={error}
              isNewReport={isNewReportSelected}
            />
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
          {hasActiveDraft && (
            <ReportDraftDialog
              isOpen={isDraftDialogOpen}
              setIsOpen={setIsDraftDialogOpen}
              draftCreatedAt={activeReportDraft.createdAt}
              onCancel={() => setIsAddingPanel(false)}
              onContinue={onContinueDraft}
              onDiscard={onDiscardDraft}
            />
          )}
        </div>
      </div>
    </Tailwind>
  );
};
