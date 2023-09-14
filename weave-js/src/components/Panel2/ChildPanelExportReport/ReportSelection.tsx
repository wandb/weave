import * as w from '@wandb/weave/core';
import React from 'react';

import {useNodeValue} from '../../../react';
import {Select} from '../../Form/Select';
import {Icon} from '../../Icon';
import {ChildPanelFullConfig} from '../ChildPanel';
import {
  customEntitySelectComps,
  customReportSelectComps,
} from './customSelectComponents';
import {EntityOption, ReportOption, useEntityAndProject} from './utils';
import {Button} from '../../Button';

type ReportSelectionProps = {
  config: ChildPanelFullConfig;
  selectedEntity: EntityOption | null;
  selectedReport: ReportOption | null;
  setSelectedEntity: (entity: EntityOption) => void;
  setSelectedReport: (report: ReportOption | null) => void;
};

export const ReportSelection = ({
  config,
  selectedEntity,
  selectedReport,
  setSelectedEntity,
  setSelectedReport,
}: ReportSelectionProps) => {
  const {entityName} = useEntityAndProject(config);

  // Get all of user's entities
  const entitiesMetaNode = w.opMap({
    arr: w.opUserEntities({user: w.opRootViewer({})}),
    mapFn: w.constFunction({row: 'entity'}, ({row}) => {
      return w.opDict({
        name: w.opEntityName({entity: row}),
        isTeam: w.opEntityIsTeam({entity: row}),
      } as any);
    }),
  });
  const entities = useNodeValue(entitiesMetaNode);

  // Get list of reports across all entities and projects
  const reportsNode = w.opEntityReports({
    enity: w.opRootEntity({
      entityName: w.constString(selectedEntity?.name ?? entityName),
    }),
  });
  const reportsMetaNode = w.opMap({
    arr: reportsNode,
    mapFn: w.constFunction({row: 'report'}, ({row}) => {
      return w.opDict({
        id: w.opReportInternalId({report: row}),
        name: w.opReportName({report: row}),
        updatedAt: w.opReportUpdatedAt({report: row}),
        projectName: w.opProjectName({
          project: w.opReportProject({report: row}),
        }),
      } as any);
    }),
  });
  const reports = useNodeValue(reportsMetaNode);

  return (
    <div className="mt-8 flex-1">
      <label
        htmlFor="entity"
        className="mb-4 block font-semibold text-moon-800">
        Entity
      </label>
      <Select<EntityOption, false>
        className="mb-16"
        aria-label="entity selector"
        isLoading={entities.loading}
        options={entities.result ?? []}
        placeholder={
          !entities.loading && entities.result.length === 0
            ? 'No entities found.'
            : 'Select an entity...'
        }
        getOptionLabel={option => option.name}
        getOptionValue={option => option.name}
        onChange={selected => {
          if (selected) {
            setSelectedEntity(selected);
            setSelectedReport(null);
          }
        }}
        menuListStyle={{
          maxHeight: 'calc(100vh - 34rem)',
        }}
        components={customEntitySelectComps}
        isSearchable
      />
      <label
        htmlFor="destination-report"
        className="mb-4 block font-semibold text-moon-800">
        Destination report
      </label>
      {selectedReport == null && (
        <Select<ReportOption, false>
          className="mb-16"
          aria-label="report selector"
          isLoading={reports.loading}
          isDisabled={
            entities.loading || reports.loading || reports.result.length === 0
          }
          options={reports.result ?? []}
          placeholder={
            !reports.loading && reports.result.length === 0
              ? 'No reports found.'
              : 'Select a report...'
          }
          getOptionLabel={option => option.name}
          getOptionValue={option => option.id ?? ''}
          value={selectedReport}
          onChange={selected => {
            if (selected != null) {
              setSelectedReport(selected);
            }
          }}
          components={customReportSelectComps}
          menuListStyle={{
            maxHeight: 'calc(100vh - 34rem)',
          }}
          isSearchable
        />
      )}
      {selectedReport != null && (
        <div className="flex rounded bg-moon-50 p-8 text-moon-800 ">
          <Icon name="report" className="shrink-0 grow-0 pt-4" />
          <div className="flex grow items-center justify-between">
            <p className="mx-8 flex  grow flex-col items-baseline gap-4">
              <span className="text-left">{selectedReport.name}</span>
              <span className="text-sm text-moon-500">
                {selectedReport.projectName}
              </span>
            </p>
            <Button
              icon="close"
              variant="ghost"
              className="flex shrink-0 text-moon-500"
              onClick={() => setSelectedReport(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
};
