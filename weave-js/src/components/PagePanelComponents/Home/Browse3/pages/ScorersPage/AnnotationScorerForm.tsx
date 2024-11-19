import {Box} from '@material-ui/core';
import React, {FC, useCallback, useState} from 'react';
import {z} from 'zod';

import {createBaseObjectInstance} from '../wfReactInterface/baseObjectClassQuery';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {sanitizeObjectId} from '../wfReactInterface/traceServerDirectClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {ScorerFormProps} from './ScorerForms';
import {ZSForm} from './ZodSchemaForm';

const AnnotationScorerFormSchema = z.object({
  Name: z.string().min(1),
  Description: z.string().optional(),
  Type: z.discriminatedUnion('type', [
    z.object({
      type: z.literal('boolean'),
    }),
    z.object({
      type: z.literal('integer'),
      minimum: z.number().optional().describe('Optional minimum value'),
      maximum: z.number().optional().describe('Optional maximum value'),
    }),
    z.object({
      type: z.literal('number'),
      minimum: z.number().optional().describe('Optional minimum value'),
      maximum: z.number().optional().describe('Optional maximum value'),
    }),
    z.object({
      type: z.literal('string'),
      max_length: z
        .number()
        .optional()
        .describe('Optional maximum length of the string'),
    }),
    z.object({
      type: z.literal('options'),
      enum: z.array(z.string()).describe('List of options to choose from'),
    }),
  ]),
});

const DEFAULT_STATE = {
  Type: {type: 'boolean'},
} as z.infer<typeof AnnotationScorerFormSchema>;

export const AnnotationScorerForm: FC<
  ScorerFormProps<z.infer<typeof AnnotationScorerFormSchema>>
> = ({data, onDataChange}) => {
  const [config, setConfig] = useState(data ?? DEFAULT_STATE);
  const [isValid, setIsValid] = useState(false);

  const handleConfigChange = useCallback(
    (newConfig: any) => {
      setConfig(newConfig);
      onDataChange(isValid, newConfig);
    },
    [isValid, onDataChange]
  );

  const handleValidChange = useCallback(
    (newIsValid: boolean) => {
      setIsValid(newIsValid);
      onDataChange(newIsValid, config);
    },
    [config, onDataChange]
  );

  return (
    <Box>
      <ZSForm
        configSchema={AnnotationScorerFormSchema}
        config={config ?? {}}
        setConfig={handleConfigChange}
        onValidChange={handleValidChange}
      />
    </Box>
  );
};

export const onAnnotationScorerSave = async (
  entity: string,
  project: string,
  data: z.infer<typeof AnnotationScorerFormSchema>,
  client: TraceServerClient
) => {
  let type = data.Type.type;
  if (type === 'options') {
    type = 'string';
  }
  return createBaseObjectInstance(client, 'AnnotationSpec', {
    obj: {
      project_id: projectIdFromParts({entity, project}),
      object_id: sanitizeObjectId(data.Name),
      val: {
        name: data.Name,
        description: data.Description,
        json_schema: {
          ...data.Type,
          type,
        },
      },
    },
  });
};
