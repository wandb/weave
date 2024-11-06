import {z} from 'zod';

const JSONTypeNames = z.enum(['boolean', 'number', 'string']);
const SimpleJsonResponseFormat = z.object({type: JSONTypeNames});
const ObjectJsonResponseFormat = z.object({
  type: z.literal('object'),
  properties: z.record(SimpleJsonResponseFormat),
  additionalProperties: z.literal(false),
});

export const ConfiguredLlmJudgeActionSchema = z.object({
  action_type: z.literal('llm_judge'),
  model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  prompt: z.string(),
  response_format: z.discriminatedUnion('type', [
    SimpleJsonResponseFormat,
    ObjectJsonResponseFormat,
  ]),
});
export type ConfiguredLlmJudgeActionType = z.infer<
  typeof ConfiguredLlmJudgeActionSchema
>;

export const ConfiguredWordCountActionSchema = z.object({
  action_type: z.literal('wordcount'),
});
export type ConfiguredWordCountActionType = z.infer<
  typeof ConfiguredWordCountActionSchema
>;

export const ActionConfigSchema = z.discriminatedUnion('action_type', [
  ConfiguredLlmJudgeActionSchema,
  ConfiguredWordCountActionSchema,
]);
export type ActionConfigType = z.infer<typeof ActionConfigSchema>;

export const AxctionDefinitionSchema = z.object({
  name: z.string(),
  config: ActionConfigSchema,
});
export type AxctionDefinitionType = z.infer<typeof AxctionDefinitionSchema>;

export const ActionDispatchFilterSchema = z.object({
  op_name: z.string(),
  sample_rate: z.number().min(0).max(1).default(1),
  configured_action_ref: z.string(),
  disabled: z.boolean().optional(),
});
export type ActionDispatchFilterType = z.infer<
  typeof ActionDispatchFilterSchema
>;
