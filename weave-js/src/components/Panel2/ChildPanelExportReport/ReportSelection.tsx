import * as w from '@wandb/weave/core';
import React, {useEffect, useMemo} from 'react';

import {useNodeValue} from '../../../react';
import {Select} from '../../Form/Select';
import {ChildPanelFullConfig} from '../ChildPanel';
import {
  customEntitySelectComps,
  customReportSelectComps,
} from './customSelectComponents';
import {
  NEW_REPORT_OPTION,
  DEFAULT_REPORT_OPTION,
  EntityOption,
  ReportOption,
  useEntityAndProject,
  GroupedReportOption,
  ProjectOption,
} from './utils';
import {SelectedExistingReport} from './SelectedExistingReport';

type ReportSelectionProps = {
  rootConfig: ChildPanelFullConfig;
  selectedEntity: EntityOption | null;
  selectedReport: ReportOption | null;
  selectedProject: ProjectOption | null;
  setSelectedEntity: (entity: EntityOption) => void;
  setSelectedReport: (report: ReportOption | null) => void;
  setSelectedProject: (project: ProjectOption | null) => void;
};

export const ReportSelection = ({
  rootConfig,
  selectedEntity,
  selectedReport,
  selectedProject,
  setSelectedEntity,
  setSelectedReport,
  setSelectedProject,
}: ReportSelectionProps) => {
  const {entityName} = useEntityAndProject(rootConfig);

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
  const selectedEntityNode = w.opRootEntity({
    entityName: w.constString(selectedEntity?.name ?? entityName),
  });

  useEffect(() => {
    // Default initial entity value based on url
    if (!entities.loading && entities.result.length > 0) {
      const foundEntity = entities.result.find(
        (item: EntityOption) => item.name === entityName
      );
      setSelectedEntity(foundEntity);
    }
  }, [entityName, entities, setSelectedEntity]);

  // Get list of reports across all entities and projects
  const reportsMetaNode = w.opMap({
    arr: w.opEntityReports({
      entity: selectedEntityNode,
    }),
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
  const reports = useNodeValue(reportsMetaNode ?? w.voidNode(), {
    skip: entities.loading,
  });
  const groupedReportOptions = useMemo(() => {
    return [
      {
        label: 'new report',
        options: [DEFAULT_REPORT_OPTION],
      },
      {
        label: 'existing reports',
        options: reports.result ?? [],
      },
    ];
  }, [reports.result]);

  // Get list of project names for the selected entity
  const projectMetaNode = w.opMap({
    arr: w.opEntityProjects({
      entity: selectedEntityNode,
    }),
    mapFn: w.constFunction({row: 'project'}, ({row}) => {
      return w.opDict({
        name: w.opProjectName({project: row}),
      } as any);
    }),
  });
  const projects = useNodeValue(projectMetaNode, {
    skip: selectedEntity == null || entities.loading,
  });

  return (
    <div className="mt-8 flex-1">
      <label
        htmlFor="entity"
        className="mb-4 block font-semibold text-moon-800">
        Entity
      </label>
      <Select<EntityOption, false>
        className="mb-16"
        id="entity selector"
        isLoading={entities.loading}
        options={entities.result ?? []}
        placeholder={
          !entities.loading && entities.result.length === 0
            ? 'No entities found.'
            : 'Select an entity...'
        }
        getOptionLabel={option => option.name}
        getOptionValue={option => option.name}
        value={selectedEntity}
        onChange={selected => {
          if (selected) {
            setSelectedEntity(selected);
            setSelectedReport(null);
          }
        }}
        components={customEntitySelectComps}
        isSearchable
      />
      <label
        htmlFor="destination-report"
        className="mb-4 block font-semibold text-moon-800">
        Destination report
      </label>
      {selectedReport != null && selectedReport.name !== NEW_REPORT_OPTION && (
        <SelectedExistingReport
          selectedReport={selectedReport}
          setSelectedReport={setSelectedReport}
        />
      )}
      {(selectedReport == null ||
        selectedReport.name === NEW_REPORT_OPTION) && (
        <>
          <Select<ReportOption, false, GroupedReportOption>
            className="mb-16"
            aria-label="report selector"
            isLoading={reports.loading}
            isDisabled={
              entities.loading || reports.loading || reports.result.length === 0
            }
            options={groupedReportOptions}
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
                setSelectedProject(null);
              }
            }}
            components={customReportSelectComps}
            groupDivider
            isSearchable
          />
        </>
      )}
      {selectedReport != null && selectedReport.name === NEW_REPORT_OPTION && (
        <>
          <label
            htmlFor="entity"
            className="mb-4 block font-semibold text-moon-800">
            Project
          </label>
          <Select<ProjectOption, false>
            className="mb-16"
            aria-label="project selector"
            isLoading={projects.loading}
            isDisabled={projects.loading || projects.result.length === 0}
            options={projects.result}
            placeholder={
              !projects.loading && projects.result.length === 0
                ? 'No projects found.'
                : 'Select a project...'
            }
            getOptionLabel={option => option.name}
            getOptionValue={option => option.name}
            value={selectedProject ?? null}
            onChange={selected => {
              if (selected != null) {
                setSelectedProject(selected);
              }
            }}
            isSearchable
          />
        </>
      )}
    </div>
  );
};
