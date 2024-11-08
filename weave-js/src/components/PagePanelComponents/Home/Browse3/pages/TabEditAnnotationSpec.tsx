import {Box} from '@mui/material';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {EditOrCreateAnnotationSpec} from '../feedback/HumanFeedback/EditOrCreateAnnotationSpec';
import {AnnotationSpec} from './wfReactInterface/generatedBaseObjectClasses.zod';
import {ObjectVersionSchema} from './wfReactInterface/wfDataModelHooksInterface';

export const TabEditAnnotationSpec = ({
  entityName,
  projectName,
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
        <EditOrCreateAnnotationSpec
          entityName={entityName}
          projectName={projectName}
          spec={spec}
        />
      </Box>
    </Tailwind>
  );
};
