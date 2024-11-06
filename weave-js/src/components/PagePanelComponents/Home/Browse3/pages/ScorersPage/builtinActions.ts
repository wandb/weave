import {z} from 'zod';

import {LlmJudgeActionSpecSchema} from '../wfReactInterface/baseObjectClasses.zod';
import {ConfiguredLlmJudgeActionFriendlySchema} from './actionTemplates';

type KnownBuiltingAction<
  A extends z.ZodTypeAny = z.ZodTypeAny,
  F extends z.ZodTypeAny = z.ZodTypeAny
> = {
  name: string;
  actionSchema: A;
  inputFriendlySchema: F;
  convert: (data: z.infer<F>) => z.infer<A>;
};

export const knownBuiltinActions: KnownBuiltingAction[] = [
  {
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
  },
];
