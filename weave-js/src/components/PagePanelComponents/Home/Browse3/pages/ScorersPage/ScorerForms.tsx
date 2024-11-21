import {Box} from '@material-ui/core';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Link} from '@wandb/weave/common/util/links';
import React, {FC} from 'react';

export interface ScorerFormProps<T> {
  data?: T;
  onDataChange: (isValid: boolean, data?: T) => void;
}

export const ProgrammaticScorerForm: FC<ScorerFormProps<any>> = ({
  data,
  onDataChange,
}) => {
  return (
    <Box
      style={{
        backgroundColor: MOON_200,
        padding: '16px',
        borderRadius: '8px',
      }}>
      Programmatic scorers must be written in Python. Please refer to the{' '}
      <Link to="https://weave-docs.wandb.ai/guides/evaluation/scorers#class-based-scorers">
        scorer documentation
      </Link>{' '}
      for more information.
    </Box>
  );
};
