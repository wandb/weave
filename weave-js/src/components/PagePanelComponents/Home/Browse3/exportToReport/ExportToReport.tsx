import {Box, Drawer} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
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

interface Option {
  label: string;
  value: string;
}

// Hook to fetch all available entities
export const useAvailableEntities = () => {
  const [loading, setLoading] = useState(false);
  const [entities, setEntities] = useState<Option[]>([]);

  useEffect(() => {
    const fetchEntities = async () => {
      setLoading(true);
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        setEntities([
          {label: 'entity1', value: 'entity1'},
          {label: 'entity2', value: 'entity2'},
          {label: 'entity3', value: 'entity3'},
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchEntities();
  }, []);

  return {entities, loading};
};

// Hook to fetch projects for a given entity
export const useAvailableProjects = (entityName: string | undefined) => {
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<Option[]>([]);

  useEffect(() => {
    const fetchProjects = async () => {
      const shouldLoad = Boolean(entityName);
      if (!shouldLoad) {
        return;
      }

      setLoading(true);
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        setProjects([
          {label: 'project1', value: 'project1'},
          {label: 'project2', value: 'project2'},
          {label: 'project3', value: 'project3'},
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, [entityName]);

  return {projects, loading};
};

// Hook to fetch reports for a given entity and project
export const useAvailableReports = (
  entityName: string | undefined,
  projectName: string | undefined
) => {
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Option[]>([]);

  useEffect(() => {
    const fetchReports = async () => {
      const shouldLoad = Boolean(entityName && projectName);
      if (!shouldLoad) {
        return;
      }

      setLoading(true);
      try {
        await new Promise(resolve => setTimeout(resolve, 5000));
        setReports([
          {label: 'report1', value: 'report1'},
          {label: 'report2', value: 'report2'},
          {label: 'report3', value: 'report3'},
        ]);
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, [entityName, projectName]);

  return {reports, loading};
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
  const handleEntityChange = (value: Option | null) => {
    const newEntity = value?.value || '';
    setSelectedEntity(newEntity);
    // Clear project and report if entity changes
    if (newEntity !== selectedEntity) {
      setSelectedProject('');
      setSelectedReport('create-new');
    }
  };

  const handleProjectChange = (value: Option | null) => {
    const newProject = value?.value || '';
    setSelectedProject(newProject);
    // Clear report if project changes
    if (newProject !== selectedProject) {
      setSelectedReport('create-new');
    }
  };

  // Fetch available options
  const {entities, loading: entitiesLoading} = useAvailableEntities();
  const {projects, loading: projectsLoading} =
    useAvailableProjects(selectedEntity);
  const {reports, loading: reportsLoading} = useAvailableReports(
    selectedEntity,
    selectedProject
  );

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

  const handleSave = () => {
    // TODO: Implement save logic
    onClose();
  };

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
