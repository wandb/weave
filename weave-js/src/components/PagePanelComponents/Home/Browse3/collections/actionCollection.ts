import {z} from 'zod';

const BuiltinActionSchema = z.object({
  action_type: z.literal('builtin'),
  name: z.enum(['llm_judge']),
  digest: z.string().default('*'),
});



export const ConfiguredActionSchema = z.object({
  name: z.string(),
  action: BuiltinActionSchema,
  config: z.record(z.string(), z.any()),
});

export const ActionDispatchFilterSchema = z.object({
  op_name: z.string(),
  sample_rate: z.number(),
  configured_action_ref: z.string(),
});

export type ActionDispatchFilter = z.infer<typeof ActionDispatchFilterSchema>;
export type ConfiguredAction = z.infer<typeof ConfiguredActionSchema>;

export type ActionAndSpec = {
  action: z.infer<typeof BuiltinActionSchema>;
  configSpec: z.Schema;
  convertToConfig: (data: any) => Record<string, any>;
};

const BuiltinActionConfigSchema = z.object({
  model: z.enum(['gpt-4o-mini', 'gpt-4o']),
  system_prompt: z.string(),
  response_format_properties: z.array(
    z.object({
      name: z.string(),
      type: z.enum(['boolean', 'number', 'string']),
      // is_required: z.boolean(),
    })
  ),
});

export const knownBuiltinActions: ActionAndSpec[] = [
  {
    action: {action_type: 'builtin', name: 'llm_judge', digest: '*'},
    configSpec: BuiltinActionConfigSchema,
    convertToConfig: (data: z.infer<typeof BuiltinActionConfigSchema>) => {
      return {
        model: data.model,
        system_prompt: data.system_prompt,
        response_format_schema: {
          type: 'object',
          properties: data.response_format_properties.reduce<
            Record<string, {type: string}>
          >((acc, prop) => {
            acc[prop.name] = {type: prop.type};
            return acc;
          }, {}),
          required: data.response_format_properties.map(prop => prop.name),
          additionalProperties: false,
        },
      };
    },
  },
];
