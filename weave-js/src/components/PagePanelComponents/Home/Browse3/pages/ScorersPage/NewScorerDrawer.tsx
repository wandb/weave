import {Box, Drawer, InputLabel} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Icon, IconName, IconNames} from '@wandb/weave/components/Icon';
import React, {FC, ReactNode, useCallback, useEffect, useState} from 'react';

import {
  ActionScorerForm,
  AnnotationScorerForm,
  ProgrammaticScorerForm,
} from './ScorerForms';

const HUMAN_ANNOTATION_LABEL = 'Human annotations';
export const HUMAN_ANNOTATION_VALUE = 'ANNOTATION';
const ACTION_LABEL = 'LLM judges';
const ACTION_VALUE = 'ACTION';
const PROGRAMMATIC_LABEL = 'Functional scorers';
const PROGRAMMATIC_VALUE = 'PROGRAMMATIC';

export type ScorerType =
  | typeof HUMAN_ANNOTATION_VALUE
  | typeof ACTION_VALUE
  | typeof PROGRAMMATIC_VALUE;
type OptionType = {label: string; value: ScorerType; icon: IconName};

interface ScorerTypeConfig extends OptionType {
  Component: FC<ScorerFormProps>;
  onSave: (formData: any) => Promise<void>;
}

export interface ScorerFormProps {
  onDataChange: (isValid: boolean, data: any) => void;
}

export const scorerTypeRecord: Record<ScorerType, ScorerTypeConfig> = {
  ANNOTATION: {
    label: HUMAN_ANNOTATION_LABEL,
    value: HUMAN_ANNOTATION_VALUE,
    icon: IconNames.UsersTeam,
    Component: AnnotationScorerForm,
    onSave: async data => {
      // Implementation for saving annotation scorer
      console.log('TODO: save annotation scorer', data);
    },
  },
  ACTION: {
    label: ACTION_LABEL,
    value: ACTION_VALUE,
    icon: IconNames.RobotServiceMember,
    Component: ActionScorerForm,
    onSave: async data => {
      // Implementation for saving action scorer
      console.log('TODO: save action scorer', data);
    },
  },
  PROGRAMMATIC: {
    label: PROGRAMMATIC_LABEL,
    value: PROGRAMMATIC_VALUE,
    icon: IconNames.CodeAlt,
    Component: ProgrammaticScorerForm,
    onSave: async data => {
      // Implementation for saving programmatic scorer
      console.log('TODO: save programmatic scorer', data);
    },
  },
};

const scorerTypeOptions: OptionType[] = Object.values(scorerTypeRecord).map(
  ({label, value, icon}) => ({label, value, icon})
);

interface NewScorerDrawerProps {
  open: boolean;
  onClose: () => void;
  initialScorerType?: ScorerType;
}

export const NewScorerDrawer: FC<NewScorerDrawerProps> = ({
  open,
  onClose,
  initialScorerType,
}) => {
  const [selectedScorerType, setSelectedScorerType] = useState<ScorerType>(
    initialScorerType ?? HUMAN_ANNOTATION_VALUE
  );
  const [formData, setFormData] = useState<any>(null);
  const [isFormValid, setIsFormValid] = useState(false);

  const setScorerTypeAndResetForm = useCallback((scorerType: ScorerType) => {
    setSelectedScorerType(scorerType);
    setFormData(null);
    setIsFormValid(false);
  }, []);

  useEffect(() => {
    setScorerTypeAndResetForm(initialScorerType ?? HUMAN_ANNOTATION_VALUE);
  }, [initialScorerType, setScorerTypeAndResetForm]);

  const handleFormDataChange = useCallback((isValid: boolean, data: any) => {
    setIsFormValid(isValid);
    setFormData(data);
  }, []);

  const onSave = useCallback(async () => {
    try {
      await scorerTypeRecord[selectedScorerType].onSave(formData);
      onClose();
    } catch (error) {
      console.error('Failed to create scorer:', error);
      // Handle error appropriately
    }
  }, [selectedScorerType, formData, onClose]);

  const ScorerFormComponent = scorerTypeRecord[selectedScorerType].Component;

  return (
    <SaveableDrawer
      open={open}
      title="Create scorer"
      onClose={onClose}
      onSave={onSave}
      saveDisabled={!isFormValid}>
      <AutocompleteWithLabel
        label="Scorer type"
        options={scorerTypeOptions}
        value={scorerTypeOptions.find(opt => opt.value === selectedScorerType)}
        formatOptionLabel={option => (
          <Box display="flex" alignItems="center" style={{gap: '4px'}}>
            <Icon name={option.icon} />
            {option.label}
          </Box>
        )}
        onChange={value =>
          value && setScorerTypeAndResetForm(value.value as ScorerType)
        }
      />
      <ScorerFormComponent onDataChange={handleFormDataChange} />
    </SaveableDrawer>
  );
};

type AutocompleteWithLabelType<Option = any> = (
  props: {
    label: string;
  } & React.ComponentProps<typeof Select<Option>>
) => React.ReactElement;

const AutocompleteWithLabel: AutocompleteWithLabelType = ({
  label,
  ...props
}) => (
  <Box style={{marginBottom: '10px', padding: '0px 2px'}}>
    <InputLabel style={{marginBottom: '10px', fontSize: '14px'}}>
      {label}
    </InputLabel>
    <Select {...props} />
  </Box>
);

interface SaveableDrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  onSave: () => void;
  saveDisabled?: boolean;
  children: ReactNode;
}

export const SaveableDrawer: FC<SaveableDrawerProps> = ({
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
            p: '10px',
            display: 'flex',
            fontWeight: 600,
          }}>
          <Box sx={{flexGrow: 1}}>{title}</Box>
          <Button size="small" variant="quiet" icon="close" onClick={onClose} />
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
            p: '10px',
          }}>
          <Button
            onClick={onSave}
            color="primary"
            disabled={saveDisabled}
            className="w-full">
            Create scorer
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};