import {Box} from '@material-ui/core';
import {Alert} from '@mui/material';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {FilterableObjectVersionsTable} from '../ObjectVersionsPage';
import {useCreateBaseObjectInstance} from '../wfReactInterface/baseObjectClassQuery';
import {ActionDefinition} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {actionTemplates} from './actionTemplates';
import {NewBuiltInActionScorerModal} from './NewBuiltInActionScorerModal';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Scorers"
      // hideTabsIfSingle
      tabs={[
        {
          label: 'Built-In Actions',
          content: <OnlineScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Human Review',
          content: <HumanScorersTab entity={entity} project={project} />,
        },
        {
          label: 'Code Scorers',
          content: <CodeScorersTab entity={entity} project={project} />,
        },
      ]}
      headerContent={undefined}
    />
  );
};

const CodeScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <FilterableObjectVersionsTable
      entity={entity}
      project={project}
      initialFilter={{
        baseObjectClass: 'Scorer',
      }}
    />
  );
};

const HumanScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <Box sx={{p: 3}}>
      <Alert severity="info">Human Review coming soon</Alert>
    </Box>
  );
  // return (
  //   <FilterableObjectVersionsTable
  //     entity={entity}
  //     project={project}
  //     initialFilter={{
  //       baseObjectClass: 'PLACEHOLDER_FOR_COLUMN_CONFIG',
  //     }}
  //   />
  // );
};

const OnlineScorersTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const createCollectionObject =
    useCreateBaseObjectInstance('ActionDefinition');
  const [lastUpdatedTimestamp, setLastUpdatedTimestamp] = useState(0);

  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleCreateBlank = () => {
    setSelectedTemplate('');
    setIsModalOpen(true);
  };

  const handleDropdownClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleTemplateSelect = (templateName: string) => {
    setSelectedTemplate(templateName);
    setIsModalOpen(true);
    handleClose();
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedTemplate('');
  };

  const handleSaveModal = (newAction: ActionDefinition) => {
    let objectId = newAction.name;
    // Remove non alphanumeric characters
    // TODO: reconcile this null-name issue
    objectId = objectId?.replace(/[^a-zA-Z0-9]/g, '-') ?? '';
    createCollectionObject({
      obj: {
        project_id: projectIdFromParts({entity, project}),
        object_id: objectId,
        val: newAction,
      },
    })
      .then(() => {
        setLastUpdatedTimestamp(Date.now());
      })
      .catch(err => {
        console.error(err);
      })
      .finally(() => {
        handleCloseModal();
      });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: '1 1 auto',
        width: '100%',
      }}>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'flex-end',
          p: 2,
          width: '100%',
        }}>
        <Box sx={{display: 'flex', alignItems: 'center'}}>
          <Button
            className="mr-1"
            size="medium"
            variant="primary"
            onClick={handleCreateBlank}
            icon="add-new">
            Create New
          </Button>
          <Button
            size="medium"
            variant="secondary"
            onClick={handleDropdownClick}
            icon="chevron-down"
            tooltip="Select a template"
          />
        </Box>
        <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
          {actionTemplates.map(template => (
            <MenuItem
              key={template.name}
              onClick={() => handleTemplateSelect(template.name)}>
              {template.name}
            </MenuItem>
          ))}
        </Menu>
      </Box>
      <FilterableObjectVersionsTable
        key={lastUpdatedTimestamp}
        entity={entity}
        project={project}
        initialFilter={{
          baseObjectClass: 'ActionDefinition',
        }}
      />
      <NewBuiltInActionScorerModal
        open={isModalOpen}
        onClose={handleCloseModal}
        onSave={handleSaveModal}
        initialTemplate={selectedTemplate}
      />
    </Box>
  );
};

export const AddNewButton: FC<{
  onClick: () => void;
  disabled?: boolean;
  tooltipText?: string;
}> = ({onClick, disabled, tooltipText}) => (
  <Box
    sx={{
      height: '100%',
      display: 'flex',
      alignItems: 'center',
    }}>
    <Button
      className="mx-4"
      size="medium"
      variant="primary"
      disabled={disabled}
      onClick={onClick}
      icon="add-new"
      tooltip={tooltipText}>
      Create New
    </Button>
  </Box>
);
