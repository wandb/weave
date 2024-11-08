import { Box } from '@mui/material';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import React, { useState } from 'react';

import { EditAnnotationSpec } from '../feedback/HumanFeedback/EditAnnotationSpec';
import { EditingState } from '../feedback/HumanFeedback/ManageHumanFeedback';
import { useCreateBaseObjectInstance } from './wfReactInterface/baseObjectClassQuery';
import { AnnotationSpec } from './wfReactInterface/generatedBaseObjectClasses.zod';
import { projectIdFromParts } from './wfReactInterface/tsDataModelHooks';
import { ObjectVersionSchema } from './wfReactInterface/wfDataModelHooksInterface';

export const TabEditAnnotationSpec = ({
  entityName,
  projectName,
  objectVersion,
}: {
  entityName: string;
  projectName: string;
  objectVersion: ObjectVersionSchema;
}) => {
  const createHumanFeedback = useCreateBaseObjectInstance('AnnotationSpec');
  const spec: AnnotationSpec = objectVersion.val;

  const [editState, setEditState] = useState<EditingState>({
    isEditing: false,
    spec,
    jsonSchema: JSON.stringify(spec.json_schema ?? {}, null, 2),
    error: '',
  });

  const onSaveSpec = (updatedSpec: AnnotationSpec) => {
    return createHumanFeedback({
      obj: {
        project_id: projectIdFromParts({
          entity: entityName,
          project: projectName,
        }),
        object_id: objectVersion.objectId,
        val: updatedSpec,
      },
    });
  };

  return (
    <Tailwind>
      <Box className="h-full p-12">
        <EditAnnotationSpec
          editState={editState}
          setEditState={setEditState}
          onSave={onSaveSpec}
        />
      </Box>
    </Tailwind>
  );
};
