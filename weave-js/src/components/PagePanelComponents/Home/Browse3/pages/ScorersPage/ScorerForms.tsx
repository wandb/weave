import {Box} from '@material-ui/core';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Link} from '@wandb/weave/common/util/links';
import React, {FC} from 'react';

import {ScorerFormProps} from './NewScorerDrawer';

export const AnnotationScorerForm: FC<ScorerFormProps> = ({onDataChange}) => {
  // Implementation for annotation scorer form
  return <div>Annotation Scorer Form</div>;
};

export const ActionScorerForm: FC<ScorerFormProps> = ({onDataChange}) => {
  // Implementation for action scorer form
  return <div>Action Scorer Form</div>;
};

export const ProgrammaticScorerForm: FC<ScorerFormProps> = ({onDataChange}) => {
  return (
    <Box
      style={{
        backgroundColor: MOON_200,
        padding: '16px',
        borderRadius: '8px',
      }}>
      Functional scorers must be written in Python. Please refer to the{' '}
      <Link to="https://weave-docs.wandb.ai/guides/evaluation/scorers#class-based-scorers">
        scorer documentation
      </Link>{' '}
      for more information.
    </Box>
  );
};
