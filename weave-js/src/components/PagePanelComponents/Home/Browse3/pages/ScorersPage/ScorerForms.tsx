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
      <Box mb={1}>
        This form will allow you to create a{' '}
        <span style={{fontWeight: 'semibold'}}>Human Annotation</span> scorer
        which can be used in the trace interface.
      </Box>
      <Box>
        If you would like to create a{' '}
        <span style={{fontWeight: 'semibold'}}>Programmatic Scorer</span>,
        please use Python and refer to the{' '}
        <Link to="https://weave-docs.wandb.ai/guides/evaluation/scorers#class-based-scorers">
          scorer documentation
        </Link>{' '}
        for more information.
      </Box>
    </Box>
  );
};
