import {Box, Typography} from '@material-ui/core';
import {MOON_200, MOON_300, MOON_600} from '@wandb/weave/common/css/color.styles';
import {Link} from '@wandb/weave/common/util/links';
import {Button} from '@wandb/weave/components/Button';
import {IconName, IconNames} from '@wandb/weave/components/Icon';
import React, {FC, useCallback, useState} from 'react';

import {ResizableDrawer} from '../common/ResizableDrawer';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import * as AnnotationScorerForm from './AnnotationScorerForm';
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
  const [formData, setFormData] = useState<any>(null);
  const [isFormValid, setIsFormValid] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(600);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const handleFormDataChange = useCallback((isValid: boolean, data: any) => {
    setIsFormValid(isValid);
    setFormData(data);
  }, []);

  const getClient = useGetTraceServerClientContext();

  const onSave = useCallback(async () => {
    try {
      await scorerTypeRecord[HUMAN_ANNOTATION_VALUE].onSave(
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
  }, [entity, project, formData, getClient, onClose]);

  const handleClose = () => {
    setFormData(null);
    onClose();
  };

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  return (
    <ResizableDrawer
      open={open}
      onClose={handleClose}
      defaultWidth={isFullscreen ? window.innerWidth - 73 : drawerWidth}
      setWidth={width => !isFullscreen && setDrawerWidth(width)}
      headerContent={
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            height: 44,
            minHeight: 44,
            pl: 4,
            pr: 2,
            borderBottom: `1px solid ${MOON_300}`,
          }}>
          <Typography
            variant="h6"
            style={{fontFamily: 'Source Sans Pro', fontWeight: 600}}>
            Create new scorer
          </Typography>
          <Box sx={{display: 'flex', marginLeft: 1}}>
            <Button
              onClick={handleToggleFullscreen}
              variant="ghost"
              icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
              tooltip={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            />
            <Button
              onClick={handleClose}
              variant="ghost"
              icon="close"
              tooltip="Close"
            />
          </Box>
        </Box>
      }>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          overflow: 'hidden',
        }}>
        <Box
          sx={{
            p: 4,
            flexGrow: 1,
            overflow: 'auto',
          }}>
          <Box
            style={{
              backgroundColor: MOON_200,
              color: MOON_600,
              padding: '16px',
              borderRadius: '8px',
            }}>
            <Box mb={1}>
              <span style={{fontWeight: '600'}}>Human Annotation</span> scorers
              can be used in the trace interface.
            </Box>
            <Box>
              To create a{' '}
              <span style={{fontWeight: '600'}}>Programmatic Scorer</span>,
              please use Python and refer to the{' '}
              <Link to="https://weave-docs.wandb.ai/guides/evaluation/scorers#class-based-scorers">
                scorer documentation
              </Link>{' '}
              for more information.
            </Box>
          </Box>

          <Box sx={{mt: 4}}>
            <AnnotationScorerForm.AnnotationScorerForm
              data={formData}
              onDataChange={handleFormDataChange}
            />
          </Box>
        </Box>
        <Box
          sx={{
            pt: '10px',
            pb: '9px',
            px: 0,
            borderTop: `1px solid ${MOON_300}`,
            bgcolor: 'background.paper',
            width: '100%',
            display: 'flex',
            flexShrink: 0,
          }}>
          <Button
            onClick={onSave}
            variant="primary"
            disabled={!isFormValid}
            style={{
              width: '100%',
              margin: '0 16px',
              borderRadius: '4px',
            }}
            twWrapperStyles={{
              width: 'calc(100% - 32px)',
              display: 'block',
            }}>
            Create Scorer
          </Button>
        </Box>
      </Box>
    </ResizableDrawer>
  );
};
