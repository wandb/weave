import {Box} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {AnnotationSpec} from './wfReactInterface/generatedBaseObjectClasses.zod';
import {ObjectVersionSchema} from './wfReactInterface/wfDataModelHooksInterface';

export const TabEditAnnotationSpec = ({
  objectVersion,
}: {
  entityName: string;
  projectName: string;
  objectVersion: ObjectVersionSchema;
}) => {
  const spec: AnnotationSpec = objectVersion.val;

  return (
    <Tailwind>
      <Box className="h-full p-12">
        <div> coming soon </div>
        <div>{spec}</div>
      </Box>
    </Tailwind>
  );
};
