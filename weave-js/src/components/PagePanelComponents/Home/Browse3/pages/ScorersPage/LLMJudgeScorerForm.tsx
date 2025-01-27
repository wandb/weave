import {Box} from '@material-ui/core';
import {
  GOLD_300,
  GOLD_550,
  GOLD_650,
} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import React, {FC, useCallback, useState} from 'react';
import {z} from 'zod';

import {LlmJudgeActionSpecSchema} from '../wfReactInterface/builtinObjectClasses.zod';
import {ActionSpecSchema} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {createBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {AutocompleteWithLabel} from './FormComponents';
import {ScorerFormProps} from './ScorerForms';
import {ZSForm} from './ZodSchemaForm';

const TEMPLATE_CTA = 'Start with a common LLM judge template!';
const JSONTypeNames = z.enum(['Boolean', 'Number', 'String']);
const ObjectJsonResponseFormat = z.object({
  Type: z.literal('Object'),
  Properties: z.record(z.string().min(1), JSONTypeNames),
});

const LLMJudgeScorerFormSchema = z.object({
  Name: z.string().min(5),
  Model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  Prompt: z.string().min(5),
  'Response Schema': z.discriminatedUnion('Type', [
    z.object({Type: z.literal('Boolean')}),
    z.object({Type: z.literal('Number')}),
    z.object({Type: z.literal('String')}),
    ObjectJsonResponseFormat,
  ]),
});

const LLMJudgeScorerTemplates: Record<
  string,
  z.infer<typeof LLMJudgeScorerFormSchema>
> = {
  RelevancyJudge: {
    Name: 'Relevancy Judge',
    Model: 'gpt-4o-mini',
    Prompt: 'Is the output relevant to the input?',
    'Response Schema': {
      Type: 'Object',
      Properties: {
        Relevance: 'Boolean',
        Reason: 'String',
      },
    },
  },
  CorrectnessJudge: {
    Name: 'Correctness Judge',
    Model: 'gpt-4o-mini',
    Prompt:
      'Given the input and output, and your knowledge of the world, is the output correct?',
    'Response Schema': {
      Type: 'Object',
      Properties: {
        Correctness: 'Boolean',
        Reason: 'String',
      },
    },
  },
};

const LLMJudgeScorerOptions = Object.entries(LLMJudgeScorerTemplates).map(
  ([name, template]) => ({
    label: template.Name,
    value: name,
  })
);

export const LLMJudgeScorerForm: FC<
  ScorerFormProps<z.infer<typeof LLMJudgeScorerFormSchema>>
> = ({data, onDataChange}) => {
  const [config, setConfigRaw] = useState(data);
  const [isValid, setIsValidRaw] = useState(false);
  const [templateKey, setTemplateKey] = useState<string>(
    Object.keys(LLMJudgeScorerTemplates)[0]
  );
  const selectedTemplate = templateKey
    ? LLMJudgeScorerTemplates[templateKey]
    : null;

  const setConfig = useCallback(
    (newConfig: any) => {
      setConfigRaw(newConfig);
      onDataChange(isValid, newConfig);
    },
    [isValid, onDataChange]
  );

  const setIsValid = useCallback(
    (newIsValid: boolean) => {
      setIsValidRaw(newIsValid);

      onDataChange(newIsValid, config);
    },
    [config, onDataChange]
  );

  return (
    <Box>
      <Box
        style={{
          padding: '10px',
          marginBottom: '10px',
          borderRadius: '10px',
          backgroundColor: GOLD_300,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: '10px',
          // overflow: 'hidden',
          flexWrap: 'wrap',
        }}>
        <Box style={{color: GOLD_650}}>{TEMPLATE_CTA}</Box>
        <Box style={{flex: 1}}>
          <AutocompleteWithLabel
            style={{marginBottom: 0}}
            value={LLMJudgeScorerOptions.find(o => o.value === templateKey)}
            onChange={v => setTemplateKey(v.value)}
            options={LLMJudgeScorerOptions}
          />
        </Box>
        <Button
          icon={IconNames.MagicWandStar}
          style={{backgroundColor: GOLD_550, flexShrink: 0}}
          disabled={!selectedTemplate}
          onClick={() => {
            if (selectedTemplate) {
              setIsValidRaw(true);
              setConfig(selectedTemplate);
            }
          }}>
          Fill
        </Button>
      </Box>
      <ZSForm
        configSchema={LLMJudgeScorerFormSchema}
        config={config ?? {}}
        setConfig={setConfig}
        onValidChange={setIsValid}
      />
    </Box>
  );
};

export const onLLMJudgeScorerSave = async (
  entity: string,
  project: string,
  data: z.infer<typeof LLMJudgeScorerFormSchema>,
  client: TraceServerClient
) => {
  let objectId = data.Name;
  objectId = objectId.replace(/[^a-zA-Z0-9]/g, '-') ?? '';

  const judgeAction: z.infer<typeof LlmJudgeActionSpecSchema> =
    LlmJudgeActionSpecSchema.parse({
      action_type: 'llm_judge',
      model: data.Model,
      prompt: data.Prompt,
      response_schema: {
        type: data['Response Schema'].Type.toLowerCase(),
        ...(data['Response Schema'].Type === 'Object'
          ? {
              properties: _.mapValues(
                data['Response Schema'].Properties,
                v => ({type: v.toLowerCase()})
              ),
            }
          : {}),
      },
    });

  const newAction: z.infer<typeof ActionSpecSchema> = ActionSpecSchema.parse({
    name: objectId,
    config: judgeAction,
  });

  return createBuiltinObjectInstance(client, 'ActionSpec', {
    obj: {
      project_id: projectIdFromParts({entity, project}),
      object_id: objectId,
      val: newAction,
    },
  });
};
