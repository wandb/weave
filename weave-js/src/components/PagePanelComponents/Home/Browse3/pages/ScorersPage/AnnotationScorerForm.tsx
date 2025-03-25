import {Box} from '@material-ui/core';
import React, {FC, useCallback, useEffect, useState} from 'react';
import {z} from 'zod';

import {createBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {sanitizeObjectId} from '../wfReactInterface/traceServerDirectClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {ScorerFormProps} from './ScorerForms';
import {ZSForm} from './ZodSchemaForm';

const AnnotationScorerFormSchema = z.object({
  Name: z.string().min(1).describe('Annotation name, shown in the interface.'),
  Description: z
    .string()
    .optional()
    .describe('Visible description of your annotation field in the interface.'),
  Type: z
    .discriminatedUnion('type', [
      z.object({
        type: z.literal('Boolean'),
      }),
      z.object({
        type: z.literal('Integer'),
        Minimum: z.number().optional(),
        Maximum: z.number().optional(),
      }),
      z.object({
        type: z.literal('Number'),
        Minimum: z.number().optional(),
        Maximum: z.number().optional(),
      }),
      z.object({
        type: z.literal('String'),
        'Maximum length': z.number().optional(),
      }),
      z.object({
        type: z.literal('Select'),
        'Select options': z.array(z.string()).min(1),
      }),
    ])
    .describe('The format of the annotation input.'),
});

const DEFAULT_STATE = {
  Type: {type: 'Boolean'},
} as z.infer<typeof AnnotationScorerFormSchema>;

export const AnnotationScorerForm: FC<
  ScorerFormProps<z.infer<typeof AnnotationScorerFormSchema>>
> = ({data, onDataChange}) => {
  const [config, setConfig] = useState(data ?? DEFAULT_STATE);
  useEffect(() => {
    setConfig(data ?? DEFAULT_STATE);
  }, [data]);
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
  const jsonSchemaType = convertTypeToJsonSchemaType(data.Type.type);
  const typeExtras = convertTypeExtrasToJsonSchema(data);
  return createBuiltinObjectInstance(client, 'AnnotationSpec', {
    obj: {
      project_id: projectIdFromParts({entity, project}),
      object_id: sanitizeObjectId(data.Name),
      val: {
        name: data.Name,
        description: data.Description,
        field_schema: {
          ...typeExtras,
          type: jsonSchemaType,
        },
      },
    },
  });
};

function convertTypeToJsonSchemaType(type: string) {
  // Special case for Options, which is a string with an enum
  if (type === 'Select') {
    return 'string';
  }
  return type.toLowerCase();
}

function convertTypeExtrasToJsonSchema(
  obj: z.infer<typeof AnnotationScorerFormSchema>
) {
  const typeSchema = obj.Type;
  const typeExtras: Record<string, any> = {};
  if (typeSchema.type === 'String') {
    typeExtras.maxLength = typeSchema['Maximum length'];
  } else if (typeSchema.type === 'Integer' || typeSchema.type === 'Number') {
    typeExtras.minimum = typeSchema.Minimum;
    typeExtras.maximum = typeSchema.Maximum;
  } else if (typeSchema.type === 'Select') {
    typeExtras.enum = typeSchema['Select options'];
  }
  return typeExtras;
}
