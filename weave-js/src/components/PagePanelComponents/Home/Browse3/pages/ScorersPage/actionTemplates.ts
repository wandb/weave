import {z} from 'zod';

const SimpleResponseFormatSchema = z
  .enum(['boolean', 'number', 'string'])
  .default('boolean');
const StructuredResponseFormatSchema = z.record(SimpleResponseFormatSchema);

const ResponseFormatSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('simple'),
    schema: SimpleResponseFormatSchema,
  }),
  z.object({
    type: z.literal('structured'),
    schema: StructuredResponseFormatSchema,
  }),
]);

export const ConfiguredLlmJudgeActionFriendlySchema = z.object({
  model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  prompt: z.string(),
  response_schema: ResponseFormatSchema,
});
type ConfiguredLlmJudgeActionFriendlyType = z.infer<
  typeof ConfiguredLlmJudgeActionFriendlySchema
>;

export const actionTemplates: Array<{
  name: string;
  type: ConfiguredLlmJudgeActionFriendlyType;
}> = [
  {
    name: 'RelevancyJudge',
    type: {
      model: 'gpt-4o-mini',
      prompt: 'Is the output relevant to the input?',
      response_schema: {
        type: 'simple',
        schema: 'boolean',
      },
    },
  },
  {
    name: 'CorrectnessJudge',
    type: {
      model: 'gpt-4o-mini',
      prompt:
        'Given the input and output, and your knowledge of the world, is the output correct?',
      response_schema: {
        type: 'structured',
        schema: {
          is_correct: 'boolean',
          reason: 'string',
        },
      },
    },
  },
];
