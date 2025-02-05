import {Box, Drawer} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, ReactNode, useState} from 'react';

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

  const handleSave = () => {
    // TODO: Implement save logic
    onClose();
  };

  const entityOptions = entityName
    ? [{label: entityName, value: entityName}]
    : [];
  const projectOptions = projectName
    ? [{label: projectName, value: projectName}]
    : [];
  const reportOptions = [{label: 'Create a new report', value: 'create-new'}];

  return (
    <SaveableDrawer
      open={isOpen}
      title="Add to report"
      onClose={onClose}
      onSave={handleSave}
      saveDisabled={!selectedEntity || !selectedProject || !selectedReport}>
      <Box display="flex" flexDirection="column">
        <AutocompleteWithLabel
          label="Entity"
          options={entityOptions}
          value={entityOptions.find(opt => opt.value === selectedEntity)}
          onChange={value => setSelectedEntity(value?.value || '')}
        />
        <AutocompleteWithLabel
          label="Project"
          options={projectOptions}
          value={projectOptions.find(opt => opt.value === selectedProject)}
          onChange={value => setSelectedProject(value?.value || '')}
        />
        <AutocompleteWithLabel
          label="Report"
          options={reportOptions}
          value={reportOptions.find(opt => opt.value === selectedReport)}
          onChange={value => setSelectedReport(value?.value || '')}
        />
      </Box>
    </SaveableDrawer>
  );
};
