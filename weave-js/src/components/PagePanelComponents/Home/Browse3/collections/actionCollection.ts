import {z} from 'zod';

const BuiltinActionSchema = z.object({
  action_type: z.literal('builtin'),
  name: z.string(),
  digest: z.string().default('*'),
});

const BuiltinActionConfigSchema = z.object({
  model: z.enum(['gpt-4o-mini', 'gpt-4o']),
  system_prompt: z.string(),
  response_format_properties: z.array(z.object({
    name: z.string(),
    type: z.enum(['text', 'number', 'boolean']),
    is_required: z.boolean(),
  })),
});

export const ActionWithConfigSchema = z.object({
  name: z.string(),
  action: BuiltinActionSchema,
  config: z.record(z.string(), z.any()),
});

export const ActionOpMappingSchema = z.object({
  name: z.string(), // Note: This field is marked for removal in the future
  action: ActionWithConfigSchema,
  op_name: z.string(),
  op_digest: z.string(),
  input_mapping: z.record(z.string()), // Input field name -> Call selector
});

export type BuiltinAction = z.infer<typeof BuiltinActionSchema>;
export type ActionWithConfig = z.infer<typeof ActionWithConfigSchema>;
export type ActionOpMapping = z.infer<typeof ActionOpMappingSchema>;




export type ActionAndSpec = {action: BuiltinAction, configSpec: z.Schema}

export const knownBuiltinActions: ActionAndSpec[] = [
    {
        action: {action_type: 'builtin',
        name: 'openai_completion',
        digest: '*',},
        configSpec: BuiltinActionConfigSchema,
    }
];