import * as w from '@wandb/weave/core';
import React, {useEffect, useMemo} from 'react';

import {useNodeValue, useValue} from '../../../react';
import {Select} from '../../Form/Select';
import {ChildPanelFullConfig} from '../ChildPanel';
import {
  customEntitySelectComps,
  customReportSelectComps,
} from './customSelectComponents';
import {SelectedExistingReport} from './SelectedExistingReport';
import {
  DEFAULT_REPORT_OPTION,
  EntityOption,
  GroupedReportOption,
  isNewReportOption,
  ProjectOption,
  ReportOption,
  useEntityAndProject,
} from './utils';

type ReportSelectionProps = {
  rootConfig: ChildPanelFullConfig;
  selectedEntity: EntityOption | null;
  selectedReport: ReportOption | null;
  selectedProject: ProjectOption | null;
  setSelectedEntity: (entity: EntityOption) => void;
  setSelectedReport: (report: ReportOption | null) => void;
  setSelectedProject: (project: ProjectOption | null) => void;
  onChange?: () => void;
};

export const ReportSelection = ({
  rootConfig,
  selectedEntity,
  selectedReport,
  selectedProject,
  setSelectedEntity,
  setSelectedReport,
  setSelectedProject,
  onChange,
}: ReportSelectionProps) => {
  const {entityName: boardEntityName, projectName: boardProjectName} =
    useEntityAndProject(rootConfig);

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
    entityName: w.constString(selectedEntity?.name ?? boardEntityName),
  });

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
  const reports = useValue(reportsMetaNode ?? w.voidNode());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => reports.refresh(), []);
  const groupedReportOptions = useMemo(() => {
    return [
      {
        options: [DEFAULT_REPORT_OPTION],
      },
      {
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
    skip:
      selectedEntity == null ||
      entities.loading ||
      !isNewReportOption(selectedReport),
  });

  useEffect(() => {
    // Default initial entity value based on board location
    if (!selectedEntity && !entities.loading && entities.result.length > 0) {
      const boardEntity = entities.result.find(
        (item: EntityOption) => item.name === boardEntityName
      );
      setSelectedEntity(boardEntity ?? null);
    }
  }, [boardEntityName, entities, selectedEntity, setSelectedEntity]);

  useEffect(() => {
    // Default report value to `New report` option if no reports are found
    if (
      selectedEntity != null &&
      !reports.loading &&
      reports.result.length === 0 &&
      selectedReport == null
    ) {
      setSelectedReport(DEFAULT_REPORT_OPTION);
    }
  }, [reports, setSelectedReport, selectedEntity, selectedReport]);

  useEffect(() => {
    // Default initial project value based on board location
    if (
      isNewReportOption(selectedReport) &&
      !selectedProject &&
      !projects.loading &&
      projects.result.length > 0
    ) {
      const boardProject = projects.result.find(
        (item: ProjectOption) => item.name === boardProjectName
      );
      setSelectedProject(boardProject ?? null);
    }
  }, [
    boardProjectName,
    projects,
    selectedProject,
    selectedReport,
    setSelectedProject,
  ]);

  return (
    <div className="flex-1">
      <label
        htmlFor="entity-selector"
        className="mb-4 block font-semibold text-moon-800">
        Entity
      </label>
      <Select<EntityOption, false>
        className="mb-16"
        id="entity-selector"
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
          onChange?.();
          if (selected) {
            setSelectedEntity(selected);
            setSelectedReport(null);
            setSelectedProject(null);
          }
        }}
        components={customEntitySelectComps}
        isSearchable
      />
      <label
        htmlFor="report-selector"
        className="mb-4 block font-semibold text-moon-800">
        Destination report
      </label>
      {selectedReport != null && !isNewReportOption(selectedReport) && (
        <SelectedExistingReport
          selectedReport={selectedReport}
          clearSelectedReport={() => {
            onChange?.();
            setSelectedReport(null);
          }}
        />
      )}
      {(selectedReport == null || isNewReportOption(selectedReport)) && (
        <>
          <Select<ReportOption, false, GroupedReportOption>
            className="mb-16"
            id="report-selector"
            isLoading={reports.loading}
            isDisabled={!selectedEntity || entities.loading || reports.loading}
            options={groupedReportOptions}
            placeholder={!reports.loading && 'Select a report...'}
            getOptionLabel={option => option.name}
            getOptionValue={option => option.id ?? ''}
            value={selectedReport}
            onChange={selected => {
              onChange?.();
              if (selected != null) {
                setSelectedReport(selected);
                setSelectedProject(
                  isNewReportOption(selected)
                    ? null
                    : {name: selected.projectName ?? ''}
                );
              }
            }}
            components={customReportSelectComps}
            groupDivider
            isSearchable
          />
        </>
      )}
      {isNewReportOption(selectedReport) && (
        <>
          <label
            htmlFor="project-selector"
            className="mb-4 block font-semibold text-moon-800">
            Project
          </label>
          <Select<ProjectOption, false>
            className="mb-16"
            id="project-selector"
            isLoading={projects.loading}
            isDisabled={
              !selectedReport ||
              projects.loading ||
              projects.result.length === 0
            }
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
              onChange?.();
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
