import * as w from '@wandb/weave/core';
import React from 'react';

import {Select} from '../../Form/Select';
import {useNodeValue} from '../../../react';
import {ChildPanelFullConfig} from '../ChildPanel';
import {EntityOption, ReportOption} from './utils';

type ReportSelectionProps = {
  config: ChildPanelFullConfig;
  selectedEntityName: string;
  selectedReport: ReportOption | null;
  setSelectedEntityName: (name: string) => void;
  setSelectedReport: (report: ReportOption | null) => void;
};

export const ReportSelection = ({
  selectedEntityName,
  selectedReport,
  setSelectedEntityName,
  setSelectedReport,
}: ReportSelectionProps) => {
  // Get all of user's entities
  const entitiesMetaNode = w.opMap({
    arr: w.opUserEntities({user: w.opRootViewer({})}),
    mapFn: w.constFunction({row: 'entity'}, ({row}) => {
      return w.opDict({
        value: w.opEntityName({entity: row}),
      } as any);
    }),
  });
  const entityNames = useNodeValue(entitiesMetaNode);

  // Get list of reports across all entities and projects
  const reportsNode = w.opEntityReports({
    enity: w.opRootEntity({
      entityName: w.constString(selectedEntityName),
    }),
  });
  const reportsMetaNode = w.opMap({
    arr: reportsNode,
    mapFn: w.constFunction({row: 'report'}, ({row}) => {
      return w.opDict({
        id: w.opReportInternalId({report: row}),
        name: w.opReportName({report: row}),
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
        isLoading={entityNames.loading}
        options={entityNames.result ?? []}
        formatOptionLabel={option => option.value}
        value={{value: selectedEntityName}}
        onChange={selected => {
          if (selected?.value) {
            setSelectedEntityName(selected.value);
            setSelectedReport(null);
          }
        }}
        isSearchable
      />
      <label
        htmlFor="destination-report"
        className="mb-4 block font-semibold text-moon-800">
        Destination report
      </label>
      <Select<ReportOption, false>
        className="mb-16"
        aria-label="report selector"
        isLoading={reports.loading}
        isDisabled={reports.loading || reports.result.length === 0}
        options={reports.result ?? []}
        placeholder={
          !reports.loading && reports.result.length === 0
            ? 'No reports found'
            : 'Select a report'
        }
        getOptionLabel={option => option.name}
        getOptionValue={option => option.id ?? ''}
        value={selectedReport}
        onChange={selected => {
          if (selected != null) {
            setSelectedReport(selected);
          }
        }}
        isSearchable
      />
    </div>
  );
};
