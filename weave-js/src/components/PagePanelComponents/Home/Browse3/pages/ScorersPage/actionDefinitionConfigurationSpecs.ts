/**
 * This file contains the definition of `actionDefinitionConfigurationSpecs` which
 * is a mapping from action type to the specification of the configuration schema
 * for that action.
 *
 * It also allows the developer to specify a more input-friendly schema
 * for that action, which is used in the UI form editor, which can be converted
 * to the action schema. It also allows the developer to specify templates for
 * that action, which are used in the UI form editor.
 */

import _ from 'lodash';
import {z} from 'zod';

import {LlmJudgeActionSpecSchema} from '../wfReactInterface/baseObjectClasses.zod';
import {ActionType} from '../wfReactInterface/generatedBaseObjectClasses.zod';

// Define `ConfiguredLlmJudgeActionFriendlySchema`
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

const ConfiguredLlmJudgeActionFriendlySchema = z.object({
  model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  prompt: z.string(),
  response_schema: ResponseFormatSchema,
});

// End of `ConfiguredLlmJudgeActionFriendlySchema`

type actionDefinitionConfigurationSpec<
  A extends z.ZodTypeAny = z.ZodTypeAny,
  F extends z.ZodTypeAny = z.ZodTypeAny
> = {
  name: string;
  actionSchema: A;
  inputFriendlySchema: F;
  convert: (data: z.infer<F>) => z.infer<A>;
  templates: Array<{
    name: string;
    config: z.infer<F>;
  }>;
};

export const actionDefinitionConfigurationSpecs: Partial<
  Record<ActionType, actionDefinitionConfigurationSpec>
> = {
  llm_judge: {
    name: 'LLM Judge',
    actionSchema: LlmJudgeActionSpecSchema,
    inputFriendlySchema: ConfiguredLlmJudgeActionFriendlySchema,
    convert: (
      data: z.infer<typeof ConfiguredLlmJudgeActionFriendlySchema>
    ): z.infer<typeof LlmJudgeActionSpecSchema> => {
      let responseFormat: z.infer<
        typeof LlmJudgeActionSpecSchema
      >['response_schema'];
      if (data.response_schema.type === 'simple') {
        responseFormat = {type: data.response_schema.schema};
      } else {
        responseFormat = {
          type: 'object',
          properties: _.mapValues(data.response_schema.schema, value => ({
            type: value as 'boolean' | 'number' | 'string',
          })),
          additionalProperties: false,
        };
      }
      return {
        action_type: 'llm_judge',
        model: data.model,
        prompt: data.prompt,
        response_schema: responseFormat,
      };
    },
    templates: [
      {
        name: 'RelevancyJudge',
        config: {
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
        config: {
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
    ],
  },
};
