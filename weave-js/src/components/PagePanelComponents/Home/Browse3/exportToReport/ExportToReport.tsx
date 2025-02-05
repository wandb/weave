import {
  gql,
  useMutation,
} from '@apollo/client';
import {Box, Drawer} from '@material-ui/core';
import {ID} from '@wandb/weave/common/util/id';
import {Button} from '@wandb/weave/components/Button/Button';
import {coreAppUrl} from '@wandb/weave/config';
import * as Urls from '@wandb/weave/core/_external/util/urls';
import React, {FC, ReactNode, useEffect, useMemo, useState} from 'react';

import {AutocompleteWithLabel} from '../pages/ScorersPage/FormComponents';
interface ExportToReportDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  entityName?: string;
  projectName?: string;
}

interface SaveableDrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  onSave: () => void;
  saveDisabled?: boolean;
  children: ReactNode;
}

// More specific types for each option type
interface EntityOption {
  label: string;
  value: string;
}

interface ProjectOption {
  label: string;
  value: string;
}

interface ReportOption {
  label: string;
  value: string;
}

interface FetchState<T> {
  data: T[];
  loading: boolean;
  error: Error | null;
}

// Hook to fetch all available entities
export const useAvailableEntities = () => {
  const [state, setState] = useState<FetchState<EntityOption>>({
    data: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    const fetchEntities = async () => {
      setState(prev => ({...prev, loading: true, error: null}));
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        if (!mounted) {
          return;
        }

        setState(prev => ({
          ...prev,
          loading: false,
          data: [
            {label: 'entity1', value: 'entity1'},
            {label: 'entity2', value: 'entity2'},
            {label: 'entity3', value: 'entity3'},
          ],
        }));
      } catch (error) {
        if (!mounted) {
          return;
        }
        setState(prev => ({
          ...prev,
          loading: false,
          error:
            error instanceof Error
              ? error
              : new Error('Failed to fetch entities'),
        }));
      }
    };

    fetchEntities();
    return () => {
      mounted = false;
    };
  }, []);

  return state;
};

// Hook to fetch projects for a given entity
export const useAvailableProjects = (entityName: string | undefined) => {
  const [state, setState] = useState<FetchState<ProjectOption>>({
    data: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    const fetchProjects = async () => {
      if (!entityName) {
        setState(prev => ({...prev, loading: false, data: [], error: null}));
        return;
      }

      setState(prev => ({...prev, loading: true, error: null}));
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        if (!mounted) {
          return;
        }

        setState(prev => ({
          ...prev,
          loading: false,
          data: [
            {label: 'project1', value: 'project1'},
            {label: 'project2', value: 'project2'},
            {label: 'project3', value: 'project3'},
          ],
        }));
      } catch (error) {
        if (!mounted) {
          return;
        }
        setState(prev => ({
          ...prev,
          loading: false,
          error:
            error instanceof Error
              ? error
              : new Error('Failed to fetch projects'),
        }));
      }
    };

    fetchProjects();
    return () => {
      mounted = false;
    };
  }, [entityName]);

  return state;
};

// Hook to fetch reports for a given entity and project
export const useAvailableReports = (
  entityName: string | undefined,
  projectName: string | undefined
) => {
  const [state, setState] = useState<FetchState<ReportOption>>({
    data: [],
    loading: false,
    error: null,
  });

  useEffect(() => {
    let mounted = true;

    const fetchReports = async () => {
      if (!entityName || !projectName) {
        setState(prev => ({...prev, loading: false, data: [], error: null}));
        return;
      }

      setState(prev => ({...prev, loading: true, error: null}));
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        if (!mounted) {
          return;
        }

        setState(prev => ({
          ...prev,
          loading: false,
          data: [
            {label: 'report1', value: 'report1'},
            {label: 'report2', value: 'report2'},
            {label: 'report3', value: 'report3'},
          ],
        }));
      } catch (error) {
        if (!mounted) {
          return;
        }
        setState(prev => ({
          ...prev,
          loading: false,
          error:
            error instanceof Error
              ? error
              : new Error('Failed to fetch reports'),
        }));
      }
    };

    fetchReports();
    return () => {
      mounted = false;
    };
  }, [entityName, projectName]);

  return state;
};

const SaveableDrawer: FC<SaveableDrawerProps> = ({
  open,
  title,
  onClose,
  onSave,
  saveDisabled,
  children,
}) => {
  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={() => {
        // do nothing - stops clicking outside from closing
        return;
      }}
      ModalProps={{
        keepMounted: true, // Better open performance on mobile
      }}>
      <Box
        sx={{
          width: '40vw',
          marginTop: '60px',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            flex: '0 0 auto',
            borderBottom: '1px solid #e0e0e0',
            px: '24px',
            py: '20px',
            display: 'flex',
            fontWeight: 600,
            fontSize: '24px',
            lineHeight: '40px',
          }}>
          <Box sx={{flexGrow: 1}}>{title}</Box>
          <Box>
            <Button
              size="large"
              variant="ghost"
              icon="close"
              onClick={onClose}
            />
          </Box>
        </Box>

        <Box
          sx={{
            flexGrow: 1,
            overflow: 'auto',
            p: 4,
          }}>
          {children}
        </Box>

        <Box
          sx={{
            display: 'flex',
            flex: '0 0 auto',
            borderTop: '1px solid #e0e0e0',
            px: '24px',
            py: '20px',
          }}>
          <Button
            onClick={onSave}
            variant="primary"
            size="large"
            disabled={saveDisabled}
            className="w-full">
            Add to report
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};

export const ExportToReportDrawer: FC<ExportToReportDrawerProps> = ({
  isOpen,
  onClose,
  entityName,
  projectName,
}) => {
  const [selectedEntity, setSelectedEntity] = useState(entityName || '');
  const [selectedProject, setSelectedProject] = useState(projectName || '');
  const [selectedReport, setSelectedReport] = useState('create-new');

  // Clear downstream selections when parent selection changes
  const handleEntityChange = (value: EntityOption | null) => {
    const newEntity = value?.value || '';
    setSelectedEntity(newEntity);
    // Clear project and report if entity changes
    if (newEntity !== selectedEntity) {
      setSelectedProject('');
      setSelectedReport('create-new');
    }
  };

  const handleProjectChange = (value: ProjectOption | null) => {
    const newProject = value?.value || '';
    setSelectedProject(newProject);
    // Clear report if project changes
    if (newProject !== selectedProject) {
      setSelectedReport('create-new');
    }
  };

  // Fetch available options
  const {
    data: entities,
    loading: entitiesLoading,
    error: entitiesError,
  } = useAvailableEntities();
  const {
    data: projects,
    loading: projectsLoading,
    error: projectsError,
  } = useAvailableProjects(selectedEntity);
  const {
    data: reports,
    loading: reportsLoading,
    error: reportsError,
  } = useAvailableReports(selectedEntity, selectedProject);

  // Clear project selection when loading starts, unless it's the default project
  useEffect(() => {
    if (
      projectsLoading &&
      !(selectedEntity === entityName && selectedProject === projectName)
    ) {
      setSelectedProject('');
    }
  }, [
    projectsLoading,
    selectedEntity,
    entityName,
    selectedProject,
    projectName,
  ]);

  // Combine provided options with fetched options
  const entityOptions = useMemo(() => {
    const defaultOption = entityName
      ? [{label: entityName, value: entityName}]
      : [];
    // During loading, only show the default option if it exists
    if (entitiesLoading) {
      return defaultOption;
    }
    return [...defaultOption, ...entities];
  }, [entityName, entities, entitiesLoading]);

  const projectOptions = useMemo(() => {
    // Only show the default project if it belongs to the selected entity
    const defaultOption =
      projectName && selectedEntity === entityName
        ? [{label: projectName, value: projectName}]
        : [];
    // During loading or if no entity selected, only show default option if valid
    if (projectsLoading || !selectedEntity) {
      return defaultOption;
    }
    return [...defaultOption, ...projects];
  }, [projectName, entityName, selectedEntity, projects, projectsLoading]);

  const reportOptions = useMemo(() => {
    const createNewOption = [
      {label: 'Create a new report', value: 'create-new'},
    ];
    // During loading or if prerequisites not met, only show create new option
    if (reportsLoading || !selectedEntity || !selectedProject) {
      return createNewOption;
    }
    return [...createNewOption, ...reports];
  }, [selectedEntity, selectedProject, reports, reportsLoading]);

  const [upsertReport] = useMutation(UPSERT_REPORT);
  const handleSave = () => {
    // TODO: Implement save logic
    upsertReport({
      variables: {
        description: '',
        displayName: 'Untitled Report',
        entityName,
        name: ID(12),
        projectName,
        spec: JSON.stringify(getEmptyReportConfig()),
        type: 'runs/draft',
      },
    }).then(result => {
      const upsertedDraft = result.data?.upsertView?.view!;
      let reportDraftPath = Urls.reportEdit(
        {
          entityName: selectedEntity,
          projectName: selectedProject,
          reportID: upsertedDraft.id,
          reportName: upsertedDraft.displayName ?? '',
        }
        // `#${documentId}`
      );
      if (reportDraftPath.startsWith('//')) {
        reportDraftPath = reportDraftPath.slice(1);
      }
      const path = coreAppUrl(reportDraftPath);
      // eslint-disable-next-line wandb/no-unprefixed-urls
      window.open(path, '_blank');
      onClose();
    });
  };

  // Show error states if any fetch failed
  if (entitiesError || projectsError || reportsError) {
    // TODO: Add proper error handling UI
    console.error(
      'Fetch error:',
      entitiesError || projectsError || reportsError
    );
  }

  return (
    <SaveableDrawer
      open={isOpen}
      title="Add to report"
      onClose={onClose}
      onSave={handleSave}
      saveDisabled={!selectedEntity || !selectedProject || !selectedReport}>
      <Box display="flex" flexDirection="column">
        <Box mb={3}>
          <AutocompleteWithLabel
            label="Entity"
            options={entityOptions}
            value={
              entityOptions.find(opt => opt.value === selectedEntity) || null
            }
            onChange={handleEntityChange}
            isLoading={entitiesLoading}
          />
        </Box>
        <Box mb={3}>
          <AutocompleteWithLabel
            label="Project"
            options={projectOptions}
            value={
              projectOptions.find(opt => opt.value === selectedProject) || null
            }
            onChange={handleProjectChange}
            isLoading={projectsLoading}
          />
        </Box>
        <Box mb={3}>
          <AutocompleteWithLabel
            label="Report"
            options={reportOptions}
            value={
              reportOptions.find(opt => opt.value === selectedReport) || null
            }
            onChange={value => setSelectedReport(value?.value || '')}
            isLoading={reportsLoading}
          />
        </Box>
      </Box>
    </SaveableDrawer>
  );
};

const UPSERT_REPORT = gql(`
    mutation UpsertReport(
      $id: ID,
      $coverUrl: String,
      $createdUsing: ViewSource,
      $description: String,
      $displayName: String,
      $entityName: String,
      $name: String,
      $parentId: ID,
      $previewUrl: String,
      $projectName: String,
      $spec: String,
      $type: String,
    ) {
      upsertView(
        input: {
          id: $id,
          coverUrl: $coverUrl,
          createdUsing: $createdUsing,
          description: $description,
          displayName: $displayName,
          entityName: $entityName,
          name: $name,
          parentId: $parentId,
          previewUrl: $previewUrl,
          projectName: $projectName,
          spec: $spec,
          type: $type,
        }
      ) {
        view {
          id
          displayName
        }
      }
    }
  `);

function getEmptyReportConfig() {
  return {
    blocks: [{type: 'paragraph', children: [{text: 'TESTING FROM WEAVE'}]}],
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

// TODO: Actually produce the correct slate note
// TODO: Implement entity/project/report selection
// TODO: Implement adding to a report, not just creating
// TODO: Refactor this to extract the report creation / addition logic into a hook