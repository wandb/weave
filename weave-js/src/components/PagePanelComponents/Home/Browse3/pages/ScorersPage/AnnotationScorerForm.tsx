
import React, { FC } from 'react';
import { createBaseObjectInstance } from '../wfReactInterface/baseObjectClassQuery';
import { TraceServerClient } from '../wfReactInterface/traceServerClient';
import { sanitizeObjectId } from '../wfReactInterface/traceServerDirectClient';
import { projectIdFromParts } from '../wfReactInterface/tsDataModelHooks';
import { ScorerFormProps } from "./ScorerForms";



export const AnnotationScorerForm: FC<ScorerFormProps<any>> = ({
  data,
  onDataChange,
}) => {
  console.log('AnnotationScorerForm', data);
  // Implementation for annotation scorer form
  return <div>Annotation Scorer Form</div>;
};

export const onAnnotationScorerSave = async (
  entity: string,
  project: string,
  data: any,
  client: TraceServerClient
) => {
  // Implementation for saving annotation scorer
  console.log('onAnnotationScorerSave', data);

  const objectId = sanitizeObjectId(data.Name);
  createBaseObjectInstance(client, 'AnnotationSpec', {
    obj: {
      project_id: projectIdFromParts({entity, project}),
      object_id: objectId,
      val: newAction,
    },
  });
};
