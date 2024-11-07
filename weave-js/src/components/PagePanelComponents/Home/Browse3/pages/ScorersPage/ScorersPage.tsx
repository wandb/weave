import {Box} from '@material-ui/core';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import {Button} from '@wandb/weave/components/Button/Button';
import React, {FC, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {FilterableObjectVersionsTable} from '../ObjectVersionsPage';
import {useCreateBaseObjectInstance} from '../wfReactInterface/baseObjectClassQuery';
import {
  ActionDefinition,
  ActionType,
} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {actionDefinitionConfigurationSpecs} from './actionDefinitionConfigurationSpecs';
import {NewActionDefinitionModal} from './NewActionDefinitionModal';

export const ScorersPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <SimplePageLayoutWithHeader
      title="Scorers"
      tabs={[
        {
          label: 'Programmatic Scorers',
          content: <CodeScorersTab entity={entity} project={project} />,
        },
        // This is a placeholder for Griffin's annotation column manager section
        // {
        //   label: 'Human Review',
        //   content: <HumanScorersTab entity={entity} project={project} />,
        // },
        {
          // It is true that this panel can show more than LLM Judges, but the
          // branding is better
          label: 'Configurable Judges',
          content: <ActionDefinitionsTab entity={entity} project={project} />,
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

const ActionDefinitionsTab: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<{
    actionType: ActionType;
    template: {name: string; config: Record<string, any>};
  } | null>(null);
  const createCollectionObject =
    useCreateBaseObjectInstance('ActionDefinition');
  const [lastUpdatedTimestamp, setLastUpdatedTimestamp] = useState(0);

  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleCreateBlank = () => {
    setSelectedTemplate(null);
    setIsModalOpen(true);
  };

  const handleDropdownClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleTemplateSelect = (template: {
    actionType: ActionType;
    template: {name: string; config: Record<string, any>};
  }) => {
    setSelectedTemplate(template);
    setIsModalOpen(true);
    handleClose();
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedTemplate(null);
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
          {Object.entries(actionDefinitionConfigurationSpecs).flatMap(
            ([actionType, spec]) =>
              spec.templates.map(template => (
                <MenuItem
                  key={template.name}
                  onClick={() =>
                    handleTemplateSelect({
                      actionType: actionType as ActionType,
                      template,
                    })
                  }>
                  {template.name}
                </MenuItem>
              ))
          )}
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
      <NewActionDefinitionModal
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
