/**
 * We have many progress/loading indicators throughout Weave:
 * - TrackedWandbLoader - based on Semantic UI loader
 * - Semantic UI's loader
 * - Material's CircularProgress
 * - WeaveAnimatedLoader (spinning logo)
 * Plus a bunch of additional derivatives and related things like skeletons in the W&B app codebase.
 *
 * This is one more loading indicator that has the following properties:
 * - Circular indeterminate progress indicator
 * - Based on Material (and not Semantic, which we want to move away from)
 * - Styled to match our color palette
 * - Easy to use inline or centered in a container
 *
 * TODO: A better solution would be consolidation, e.g. updating TrackedWandbLoader,
 * but that is a riskier change than we want to make right now because of how many
 * places it is used.
 */

import {Box} from '@mui/material';
import CircularProgress, {
  CircularProgressProps,
} from '@mui/material/CircularProgress';
import React from 'react';

import * as Colors from '../common/css/color.styles';

type LoadingProps = CircularProgressProps & {
  centered?: boolean;
};

export const Loading = ({centered, ...props}: LoadingProps) => {
  const circle = (
    <CircularProgress
      {...props}
      sx={{
        color: (theme: any) => Colors.TEAL_500,
      }}
    />
  );
  if (centered) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}>
        {circle}
      </Box>
    );
  }
  return circle;
};
