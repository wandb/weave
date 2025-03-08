import {Box, Drawer} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Icon, IconName, IconNames} from '@wandb/weave/components/Icon';
import React, {
  FC,
  ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import * as AnnotationScorerForm from './AnnotationScorerForm';
import {AutocompleteWithLabel} from './FormComponents';
import * as LLMJudgeScorerForm from './LLMJudgeScorerForm';
import {ProgrammaticScorerForm, ScorerFormProps} from './ScorerForms';

const HUMAN_ANNOTATION_LABEL = 'Human annotation';
export const HUMAN_ANNOTATION_VALUE = 'ANNOTATION';
const LLM_JUDGE_LABEL = 'LLM judge';
export const LLM_JUDGE_VALUE = 'LLM_JUDGE';
const PROGRAMMATIC_LABEL = 'Programmatic scorer';
const PROGRAMMATIC_VALUE = 'PROGRAMMATIC';

export type ScorerType =
  | typeof HUMAN_ANNOTATION_VALUE
  | typeof LLM_JUDGE_VALUE
  | typeof PROGRAMMATIC_VALUE;
type OptionType = {label: string; value: ScorerType; icon: IconName};

interface ScorerTypeConfig<T> extends OptionType {
  Component: FC<ScorerFormProps<T>>;
  onSave: (
    entity: string,
    project: string,
    formData: T,
    client: TraceServerClient
  ) => Promise<any>;
}

export const scorerTypeRecord: Record<ScorerType, ScorerTypeConfig<any>> = {
  ANNOTATION: {
    label: HUMAN_ANNOTATION_LABEL,
    value: HUMAN_ANNOTATION_VALUE,
    icon: IconNames.UsersTeam,
    Component: AnnotationScorerForm.AnnotationScorerForm,
    onSave: AnnotationScorerForm.onAnnotationScorerSave,
  },
  LLM_JUDGE: {
    label: LLM_JUDGE_LABEL,
    value: LLM_JUDGE_VALUE,
    icon: IconNames.RobotServiceMember,
    Component: LLMJudgeScorerForm.LLMJudgeScorerForm,
    onSave: LLMJudgeScorerForm.onLLMJudgeScorerSave,
  },
  PROGRAMMATIC: {
    label: PROGRAMMATIC_LABEL,
    value: PROGRAMMATIC_VALUE,
    icon: IconNames.CodeAlt,
    Component: ProgrammaticScorerForm,
    onSave: async (entity, project, data, client) => {
      // Implementation for saving programmatic scorer
      console.log('TODO: save programmatic scorer', data);
    },
  },
};

const scorerTypeOptions: OptionType[] = Object.values(scorerTypeRecord).map(
  ({label, value, icon}) => ({label, value, icon})
);

interface NewScorerDrawerProps {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  initialScorerType?: ScorerType;
}

export const NewScorerDrawer: FC<NewScorerDrawerProps> = ({
  entity,
  project,
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

  const getClient = useGetTraceServerClientContext();

  const onSave = useCallback(async () => {
    try {
      await scorerTypeRecord[selectedScorerType].onSave(
        entity,
        project,
        formData,
        getClient()
      );
      onClose();
      setFormData(null);
    } catch (error) {
      console.error('Failed to create scorer:', error);
      // Handle error appropriately
    }
  }, [selectedScorerType, entity, project, formData, getClient, onClose]);

  const ScorerFormComponent = scorerTypeRecord[selectedScorerType].Component;

  // Here, we hide the LLM judge option from non-admins since the
  // feature is in active development. We want to be able to get
  // feedback without enabling for all users.
  const options = useMemo(() => {
    return scorerTypeOptions.filter(opt => opt.value !== LLM_JUDGE_VALUE);
  }, []);

  const handleClose = () => {
    setFormData(null);
    onClose();
  };

  return (
    <SaveableDrawer
      open={open}
      title="Create scorer"
      onClose={handleClose}
      onSave={onSave}
      saveDisabled={!isFormValid}>
      <AutocompleteWithLabel
        label="Scorer type"
        options={options}
        value={options.find(opt => opt.value === selectedScorerType)}
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
      <ScorerFormComponent
        data={formData}
        onDataChange={handleFormDataChange}
      />
    </SaveableDrawer>
  );
};

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
            color="primary"
            size="large"
            disabled={saveDisabled}
            className="w-full">
            Create scorer
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
