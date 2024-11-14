import {Box} from '@material-ui/core';
import {GOLD_300, GOLD_650} from '@wandb/weave/common/css/color.styles';
import React, {FC, useCallback, useState} from 'react';
import {z} from 'zod';

import {ScorerFormProps} from './ScorerForms';
import {ZSForm} from './ZodSchemaForm';
import { Icon, IconNames } from '@wandb/weave/components/Icon';
import { AutocompleteWithLabel } from './FormComponents';

const JSONTypeNames = z.enum(['Boolean', 'Number', 'String']);
const ObjectJsonResponseFormat = z.object({
  Type: z.literal('Object'),
  Properties: z.record(JSONTypeNames),
});

const LLMJudgeScorerFormSchema = z.object({
  Name: z.string().min(5),
  Description: z.string().optional(),
  Model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  Prompt: z.string(),
  'Response Schema': z.discriminatedUnion('Type', [
    z.object({Type: z.literal('Boolean')}),
    z.object({Type: z.literal('Number')}),
    z.object({Type: z.literal('String')}),
    ObjectJsonResponseFormat,
  ]),
});

export const LLMJudgeScorerForm: FC<
  ScorerFormProps<z.infer<typeof LLMJudgeScorerFormSchema>>
> = ({data, onDataChange}) => {
  const [config, setConfigRaw] = useState(data);
  const [isValid, setIsValidRaw] = useState(false);

  const setConfig = useCallback(
    (newConfig: any) => {
      setConfigRaw(newConfig);
      onDataChange(isValid, newConfig);
    },
    [isValid, onDataChange]
  );

  const setIsValid = useCallback(
    (newIsValid: boolean) => {
      setIsValidRaw(newIsValid);

      onDataChange(newIsValid, config);
    },
    [config, onDataChange]
  );

  return (
    <Box>
      <Box
        style={{
          padding: '10px',
          marginBottom: '10px',
          borderRadius: '10px',
          backgroundColor: GOLD_300,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: '10px',
          overflow: 'hidden',
          flexWrap: 'wrap'
        }}>
        <Icon name={IconNames.MagicWandStar} style={{color: GOLD_650, flexShrink: 0}}/>
          <Box style={{color: GOLD_650}}>Begin with a common LLM Judge template!</Box>
          <Box style={{flex: 1}}><AutocompleteWithLabel style={{marginBottom: 0}} options={[
            {
              label: 'gpt-4o-mini',
              value: 'gpt-4o-mini',
            },
            {
              label: 'gpt-4o',
              value: 'gpt-4o',
            },
          ]} /></Box>
        </Box>
      <ZSForm
        configSchema={LLMJudgeScorerFormSchema}
        config={config ?? {}}
        setConfig={setConfig}
        onValidChange={setIsValid}
      />
    </Box>
  );

  // const [name, setName] = useState<string>('');
  // const [selectedActionType, setSelectedActionType] =
  //   useState<ActionType>('llm_judge');
  // const [config, setConfig] = useState<Record<string, any>>({});
  // const selectedActionSpecConfigurationSpec =
  //   actionSpecConfigurationSpecs[selectedActionType];

  // useEffect(() => {
  //   if (initialTemplate) {
  //     setConfig(initialTemplate.template.config);
  //     setSelectedActionType(initialTemplate.actionType);
  //     setName(initialTemplate.template.name);
  //   } else {
  //     setConfig({});
  //     setName('');
  //   }
  // }, [initialTemplate]);

  // const handleSave = () => {
  //   if (!selectedActionSpecConfigurationSpec) {
  //     return;
  //   }
  //   const newAction = ActionSpecSchema.parse({
  //     name,
  //     config: selectedActionSpecConfigurationSpec.convert(config as any),
  //   });
  //   onSave(newAction);
  //   setConfig({});
  //   setSelectedActionType('llm_judge');
  //   setName('');
  // };

  // const [isValid, setIsValid] = useState(false);

  // return (
  //   <ReusableDrawer
  //     open={open}
  //     title="Configure Scorer"
  //     onClose={onClose}
  //     onSave={handleSave}
  //     saveDisabled={!isValid || name === ''}>
  //     <TextField
  //       fullWidth
  //       label="Name"
  //       value={name}
  //       onChange={e => setName(e.target.value)}
  //       margin="normal"
  //     />
  //     <FormControl fullWidth margin="normal">
  //       <InputLabel>Action Type</InputLabel>
  //       <Select
  //         value={selectedActionType}
  //         onChange={e => setSelectedActionType(e.target.value as ActionType)}>
  //         {Object.entries(actionSpecConfigurationSpecs).map(
  //           ([actionType, spec], ndx) => (
  //             <MenuItem key={actionType} value={actionType}>
  //               {spec.name}
  //             </MenuItem>
  //           )
  //         )}
  //       </Select>
  //     </FormControl>
  //     {selectedActionSpecConfigurationSpec && (
  //       <div style={{margin: '0px 2px'}}>
  //         <ZSForm
  //           configSchema={
  //             selectedActionSpecConfigurationSpec.inputFriendlySchema
  //           }
  //           config={config}
  //           setConfig={setConfig}
  //           onValidChange={setIsValid}
  //         />
  //       </div>
  //     )}
  //   </ReusableDrawer>
  // );
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
