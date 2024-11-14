import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@material-ui/core';
import React, {FC, useEffect, useState} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {ZSForm} from '../../ZodSchemaForm/ZodSchemaForm';
import {
  ActionSpec,
  ActionSpecSchema,
  ActionType,
} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {actionSpecConfigurationSpecs} from './actionSpecConfigurations';

interface NewActionSpecModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionSpec) => void;
  initialTemplate?: {
    actionType: ActionType;
    template: {name: string; config: Record<string, any>};
  } | null;
}

export const NewActionSpecModal: FC<NewActionSpecModalProps> = ({
  open,
  onClose,
  onSave,
  initialTemplate,
}) => {
  const [name, setName] = useState<string>('');
  const [selectedActionType, setSelectedActionType] =
    useState<ActionType>('llm_judge');
  const [config, setConfig] = useState<Record<string, any>>({});
  const selectedActionSpecConfigurationSpec =
    actionSpecConfigurationSpecs[selectedActionType];

  useEffect(() => {
    if (initialTemplate) {
      setConfig(initialTemplate.template.config);
      setSelectedActionType(initialTemplate.actionType);
      setName(initialTemplate.template.name);
    } else {
      setConfig({});
      setName('');
    }
  }, [initialTemplate]);

  const handleSave = () => {
    if (!selectedActionSpecConfigurationSpec) {
      return;
    }
    const newAction = ActionSpecSchema.parse({
      name,
      config: selectedActionSpecConfigurationSpec.convert(config as any),
    });
    onSave(newAction);
    setConfig({});
    setSelectedActionType('llm_judge');
    setName('');
  };

  const [isValid, setIsValid] = useState(false);

  return (
    <ReusableDrawer
      open={open}
      title="Configure Scorer"
      onClose={onClose}
      onSave={handleSave}
      saveDisabled={!isValid || name === ''}>
      <TextField
        fullWidth
        label="Name"
        value={name}
        onChange={e => setName(e.target.value)}
        margin="normal"
      />
      <FormControl fullWidth margin="normal">
        <InputLabel>Action Type</InputLabel>
        <Select
          value={selectedActionType}
          onChange={e => setSelectedActionType(e.target.value as ActionType)}>
          {Object.entries(actionSpecConfigurationSpecs).map(
            ([actionType, spec], ndx) => (
              <MenuItem key={actionType} value={actionType}>
                {spec.name}
              </MenuItem>
            )
          )}
        </Select>
      </FormControl>
      {selectedActionSpecConfigurationSpec && (
        <div style={{margin: '0px 2px'}}>
          <ZSForm
            configSchema={
              selectedActionSpecConfigurationSpec.inputFriendlySchema
            }
            config={config}
            setConfig={setConfig}
            onValidChange={setIsValid}
          />
        </div>
      )}
    </ReusableDrawer>
  );
};


// const [isModalOpen, setIsModalOpen] = useState(false);
//   const [selectedTemplate, setSelectedTemplate] = useState<{
//     actionType: ActionType;
//     template: {name: string; config: Record<string, any>};
//   } | null>(null);
//   const createCollectionObject = useCreateBaseObjectInstance('ActionSpec');
//   const [lastUpdatedTimestamp, setLastUpdatedTimestamp] = useState(0);

//   const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
//   const open = Boolean(anchorEl);

//   const handleCreateBlank = () => {
//     setSelectedTemplate(null);
//     setIsModalOpen(true);
//   };

//   const handleDropdownClick = (event: React.MouseEvent<HTMLButtonElement>) => {
//     setAnchorEl(event.currentTarget);
//   };

//   const handleClose = () => {
//     setAnchorEl(null);
//   };

//   const handleTemplateSelect = (template: {
//     actionType: ActionType;
//     template: {name: string; config: Record<string, any>};
//   }) => {
//     setSelectedTemplate(template);
//     setIsModalOpen(true);
//     handleClose();
//   };

//   const handleCloseModal = () => {
//     setIsModalOpen(false);
//     setSelectedTemplate(null);
//   };

//   const handleSaveModal = (newAction: ActionSpec) => {
//     let objectId = newAction.name;
//     // Remove non alphanumeric characters
//     // TODO: reconcile this null-name issue
//     objectId = objectId?.replace(/[^a-zA-Z0-9]/g, '-') ?? '';
//     createCollectionObject({
//       obj: {
//         project_id: projectIdFromParts({entity, project}),
//         object_id: objectId,
//         val: newAction,
//       },
//     })
//       .then(() => {
//         setLastUpdatedTimestamp(Date.now());
//       })
//       .catch(err => {
//         console.error(err);
//       })
//       .finally(() => {
//         handleCloseModal();
//       });
//   };


// <Box
// sx={{
//   display: 'flex',
//   flexDirection: 'row',
//   justifyContent: 'flex-end',
//   p: 2,
//   width: '100%',
// }}>
// <Box sx={{display: 'flex', alignItems: 'center'}}>
//   <Button
//     className="mr-1"
//     size="medium"
//     variant="primary"
//     onClick={handleCreateBlank}
//     icon="add-new">
//     Create New
//   </Button>
//   <Button
//     size="medium"
//     variant="secondary"
//     onClick={handleDropdownClick}
//     icon="chevron-down"
//     tooltip="Select a template"
//   />
// </Box>
// <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
//   {Object.entries(actionSpecConfigurationSpecs).flatMap(
//     ([actionType, spec]) =>
//       spec.templates.map(template => (
//         <MenuItem
//           key={template.name}
//           onClick={() =>
//             handleTemplateSelect({
//               actionType: actionType as ActionType,
//               template,
//             })
//           }>
//           {template.name}
//         </MenuItem>
//       ))
//   )}
// </Menu>
// </Box>