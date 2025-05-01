import {Box} from '@mui/material';
import {
  MOON_100,
  MOON_200,
  MOON_500,
  MOON_800,
  MOON_900,
  OBLIVION,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import ReactDOM from 'react-dom';
import {components, OptionProps} from 'react-select';

import {Link} from '../../common/Links';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {
  findMaxTokensByModelName,
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';
import {
  OptionalSavedPlaygroundModelParams,
  PlaygroundResponseFormats,
} from '../types';
import {ProviderStatus} from '../useConfiguredProviders';
import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParams,
} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';

export interface LLMOption {
  subLabel?: string | React.ReactNode;
  label: string;
  value: LLMMaxTokensKey | string;
  max_tokens: number;
  baseModelId?: LLMMaxTokensKey | null;
  defaultParams?: OptionalSavedPlaygroundModelParams;
  provider?: string;
}

export interface ProviderOption {
  label: string | React.ReactNode;
  value: string;
  llms: Array<LLMOption>;
  isDisabled?: boolean;
}

export interface CustomOptionProps extends OptionProps<ProviderOption, false> {
  onChange: (
    value: LLMMaxTokensKey,
    maxTokens: number,
    savedModel?: {
      name: string | null;
      savedModelParams: OptionalSavedPlaygroundModelParams | null;
    }
  ) => void;
  entity: string;
  project: string;
  isAdmin?: boolean;
  onConfigureProvider?: (provider: string) => void;
}

export const DisabledProviderTooltip: React.FC<{
  children: React.ReactNode;
  entity: string;
  isAdmin?: boolean;
}> = ({children, entity, isAdmin = false}) => {
  return (
    <Tooltip
      trigger={children}
      aria-label="Provider configuration status"
      content={
        <Box
          sx={{
            backgroundColor: MOON_900,
            color: 'white',
            fontSize: '14px',
            fontWeight: 400,
            borderRadius: '4px',
          }}>
          <div>This provider is not configured.</div>
          <div>
            Check{' '}
            {isAdmin ? (
              <Link
                to={`/${entity}/settings`}
                target="_blank"
                aria-label="Go to team settings to configure missing secrets"
                rel="noopener noreferrer"
                style={{
                  color: TEAL_500,
                  textDecoration: 'none',
                }}
                className="hover:opacity-80">
                missing secrets
              </Link>
            ) : (
              'missing secrets'
            )}{' '}
            to enable it.
          </div>
        </Box>
      }
    />
  );
};

const SubMenu = ({
  llms,
  onChange,
  position,
  onSelect,
}: {
  llms: Array<LLMOption>;
  onChange: (
    value: LLMMaxTokensKey,
    maxTokens: number,
    savedModel?: {
      name: string | null;
      savedModelParams: OptionalSavedPlaygroundModelParams | null;
    }
  ) => void;
  position: {top: number; left: number};
  onSelect: () => void;
}) => {
  return ReactDOM.createPortal(
    <Box
      sx={{
        position: 'fixed',
        left: position.left - 4,
        top: position.top - 6,
        backgroundColor: 'white',
        boxShadow: '0 2px 8px ' + hexToRGB(OBLIVION, 0.15),
        borderRadius: '4px',
        width: '300px',
        maxHeight: '400px',
        overflowY: 'auto',
        border: '1px solid ' + hexToRGB(OBLIVION, 0.1),
        p: '6px',
        zIndex: 1,
      }}>
      {llms.map((llm, index) => (
        <Box
          key={llm.value}
          onClick={e => {
            e.preventDefault();
            e.stopPropagation();
            onChange(
              llm.value as LLMMaxTokensKey,
              llm.max_tokens,
              llm.defaultParams && llm.baseModelId
                ? {
                    name: llm.baseModelId,
                    savedModelParams: llm.defaultParams,
                  }
                : undefined
            );
            onSelect();
          }}
          sx={{
            width: '100%',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
            p: '6px',
            cursor: 'pointer',
            borderRadius: '4px',
            '&:hover': {
              backgroundColor: hexToRGB(OBLIVION, 0.04),
            },
          }}>
          {llm.label}
          {llm.subLabel && (
            <Box sx={{fontSize: '12px', color: MOON_500}}>{llm.subLabel}</Box>
          )}
        </Box>
      ))}
    </Box>,
    document.body
  );
};

const SubMenuOption = ({
  children,
  onChange,
  entity,
  project,
  isAdmin,
  onConfigureProvider,
  ...props
}: CustomOptionProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const [position, setPosition] = useState({top: 0, left: 0});
  const optionRef = useRef<HTMLDivElement>(null);
  const {llms, isDisabled} = props.data;

  useEffect(() => {
    if (isHovered && optionRef.current) {
      const rect = optionRef.current.getBoundingClientRect();
      setPosition({
        top: rect.top,
        left: rect.right + 4,
      });
    }
  }, [isHovered]);

  const optionContent = React.useMemo(
    () => (
      <Box
        ref={optionRef}
        onMouseEnter={() => !isDisabled && setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        sx={{
          position: 'relative',
          width: '100%',
          opacity: isDisabled ? 0.5 : 1,
        }}>
        <Box sx={{position: 'relative', zIndex: 1}}>
          <components.Option {...props}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}>
              <Box
                sx={{
                  wordBreak: 'break-all',
                  wordWrap: 'break-word',
                  whiteSpace: 'normal',
                  width: '90%',
                }}>
                {children}
              </Box>
              <Box sx={{display: 'flex', gap: 1, alignItems: 'center'}}>
                {isAdmin && isDisabled && (
                  <Button
                    variant="ghost"
                    size="small"
                    onClick={e => {
                      e.preventDefault();
                      e.stopPropagation();
                      onConfigureProvider?.(props.data.value);
                    }}>
                    Configure
                  </Button>
                )}
                {llms.length > 0 && (
                  <Icon name="chevron-next" color="moon_500" />
                )}
              </Box>
            </Box>
          </components.Option>
        </Box>
        {isHovered && llms.length > 0 && (
          <SubMenu
            llms={llms}
            onChange={onChange}
            position={position}
            onSelect={() => {
              props.selectProps.onInputChange?.('', {
                action: 'set-value',
                prevInputValue: props.selectProps.inputValue,
              });
              props.selectProps.onMenuClose?.();
            }}
          />
        )}
      </Box>
    ),
    [
      isAdmin,
      children,
      isDisabled,
      isHovered,
      llms,
      onChange,
      position,
      props,
      onConfigureProvider,
    ]
  );

  if (props.data.value === 'divider') {
    return (
      <Box
        sx={{
          borderBottom: `1px solid ${MOON_200}`,
          mb: 1,
        }}
      />
    );
  }

  return isDisabled && !isAdmin ? (
    <DisabledProviderTooltip entity={entity} isAdmin={isAdmin}>
      {optionContent}
    </DisabledProviderTooltip>
  ) : (
    optionContent
  );
};

export const CustomOption = ({
  children,
  onChange,
  entity,
  project,
  isAdmin,
  onConfigureProvider,
  ...props
}: CustomOptionProps) => {
  const {inputValue} = props.selectProps;
  // If searching, show nested structure
  if (inputValue) {
    const {llms, isDisabled} = props.data;
    if (isDisabled) {
      return null;
    }

    const filteredLLMs = llms.filter(llm =>
      llm.value.toLowerCase().includes(inputValue.toLowerCase())
    );

    return (
      <Box>
        <Box
          sx={{
            padding: '4px 12px 0',
            color: MOON_800,
            fontWeight: 600,
            cursor: 'default',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
          }}>
          <span>{props.data.label}</span>
          {isAdmin && isDisabled && (
            <Button
              variant="ghost"
              size="small"
              onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                onConfigureProvider?.(props.data.value);
              }}>
              Configure
            </Button>
          )}
        </Box>
        <Box
          sx={{
            px: '4px',
            wordBreak: 'break-all',
            wordWrap: 'break-word',
            whiteSpace: 'normal',
          }}>
          {filteredLLMs.map(llm => (
            <Box
              key={llm.value}
              onClick={() => {
                onChange(
                  llm.value as LLMMaxTokensKey,
                  llm.max_tokens,
                  llm.defaultParams && llm.baseModelId
                    ? {
                        name: llm.baseModelId,
                        savedModelParams: llm.defaultParams,
                      }
                    : undefined
                );
                props.selectProps.onInputChange?.('', {
                  action: 'set-value',
                  prevInputValue: props.selectProps.inputValue,
                });
                props.selectProps.onMenuClose?.();
              }}
              sx={{
                padding: '8px 12px',
                cursor: 'pointer',
                borderRadius: '4px',
                '&:hover': {
                  backgroundColor: MOON_100,
                },
              }}>
              {llm.label}
            </Box>
          ))}
        </Box>
      </Box>
    );
  }
  // If not searching, use the hover submenu
  return (
    <SubMenuOption
      {...props}
      onChange={onChange}
      entity={entity}
      project={project}
      isAdmin={isAdmin}
      onConfigureProvider={onConfigureProvider}>
      {children}
    </SubMenuOption>
  );
};

export const dividerOption: ProviderOption = {
  label: '',
  value: 'divider',
  llms: [],
};

export const addProviderOption: ProviderOption = {
  label: (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
      }}>
      <Icon name="add-new" />
      Add AI provider
    </Box>
  ),
  value: 'add-provider',
  llms: [],
};

export const getLLMDropdownOptions = (
  configuredProviders: Record<string, ProviderStatus>,
  configuredProvidersLoading: boolean,
  customProvidersResult: TraceObjSchemaForBaseObjectClass<'Provider'>[],
  customProviderModelsResult: TraceObjSchemaForBaseObjectClass<'ProviderModel'>[],
  customLoading: boolean,
  savedModelsResult: TraceObjSchemaForBaseObjectClass<'LLMStructuredCompletionModel'>[],
  savedModelsLoading: boolean
) => {
  const options: ProviderOption[] = [];
  const disabledOptions: ProviderOption[] = [];
  const savedModelsOptions: ProviderOption[] = [];

  if (configuredProvidersLoading) {
    options.push({
      label: 'Loading providers...',
      value: 'loading',
      llms: [],
    });
  } else {
    Object.entries(configuredProviders).forEach(([provider, {status}]) => {
      const providerLLMs = Object.entries(LLM_MAX_TOKENS)
        .filter(([_, config]) => config.provider === provider)
        .map(([llmKey]) => ({
          label: llmKey,
          value: llmKey as LLMMaxTokensKey,
          max_tokens: LLM_MAX_TOKENS[llmKey as LLMMaxTokensKey].max_tokens,
        }));

      const option = {
        label:
          LLM_PROVIDER_LABELS[provider as keyof typeof LLM_PROVIDER_LABELS],
        value: provider,
        llms: status ? providerLLMs : [],
        isDisabled: !status,
      };

      if (!status) {
        disabledOptions.push(option);
      } else {
        options.push(option);
      }
    });
  }

  // Add custom providers
  if (!customLoading) {
    customProvidersResult?.forEach(provider => {
      const providerName = provider.val.name || '';
      const currentProviderModels =
        customProviderModelsResult?.filter(
          obj => obj.val.provider === provider.digest
        ) || [];

      const shortenedProviderLabel =
        providerName.length > 20
          ? providerName.slice(0, 2) + '...' + providerName.slice(-4)
          : providerName;

      const llmOptions = currentProviderModels.map(model => ({
        label: shortenedProviderLabel + '/' + model.val.name,
        value: (provider.val.name + '/' + model.val.name) as LLMMaxTokensKey,
        max_tokens: model.val.max_tokens,
      }));

      if (llmOptions.length > 0) {
        options.push({
          label: providerName,
          value: providerName,
          llms: llmOptions,
        });
      }
    });
  }

  const savedModels = useMemo(() => {
    const savedModels: LLMOption[] = [];

    if (savedModelsResult) {
      savedModelsResult.forEach(savedModelObj => {
        const savedModelVal = savedModelObj.val as LlmStructuredCompletionModel;
        const baseModelId = savedModelVal.llm_model_id;
        const savedModelName =
          savedModelVal.name ?? savedModelObj.object_id ?? 'Unnamed Model';

        let provider: string | undefined;
        let maxTokens: number | undefined;

        // Try to determine provider from built-in model list
        if (baseModelId in LLM_MAX_TOKENS) {
          const baseModelConfig =
            LLM_MAX_TOKENS[baseModelId as LLMMaxTokensKey];
          provider = baseModelConfig.provider;
          maxTokens = baseModelConfig.max_tokens;
        } else {
          // Try to determine from custom provider models
          const customModelMatch = customProviderModelsResult?.find(
            customModel => {
              const customProviderMatch = customProvidersResult?.find(
                p => p.digest === customModel.val.provider
              );
              return (
                `${customProviderMatch?.val.name}/${customModel.val.name}` ===
                baseModelId
              );
            }
          );

          if (customModelMatch) {
            const customProviderMatch = customProvidersResult?.find(
              p => p.digest === customModelMatch.val.provider
            );
            provider = customProviderMatch?.val.name ?? undefined;
            maxTokens = customModelMatch.val.max_tokens;
          }
        }

        // Fallback max tokens determination
        if (maxTokens === undefined) {
          maxTokens = findMaxTokensByModelName(baseModelId);
        }

        savedModels.push({
          label: savedModelName,
          value: savedModelName,
          provider: provider,
          subLabel: baseModelId,
          baseModelId: baseModelId as LLMMaxTokensKey,
          max_tokens: maxTokens,
          defaultParams: convertDefaultParamsToOptionalPlaygroundModelParams(
            savedModelVal.default_params ?? {messages_template: []}
          ),
        });
      });
    }

    return savedModels;
  }, [savedModelsResult, customProviderModelsResult, customProvidersResult]);

  if (!savedModelsLoading && savedModels.length > 0) {
    savedModelsOptions.push({
      label: 'Saved Models',
      value: 'saved-models',
      llms: savedModels,
    });
  }

  // Combine enabled and disabled options
  // Add a divider option before the add provider option
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const allOptions = [
    ...options,
    ...savedModelsOptions,
    ...disabledOptions,
    dividerOption,
    addProviderOption,
  ];

  return allOptions;
};

// Helper function to convert saved model parameters to playground format
const convertDefaultParamsToOptionalPlaygroundModelParams = (
  defaultParams: LlmStructuredCompletionModelDefaultParams | null | undefined
): OptionalSavedPlaygroundModelParams => {
  if (!defaultParams) return {};

  // Helper function to convert null or undefined to undefined
  const nullToUndefined = (value: any) => {
    return value === null || value === undefined ? undefined : value;
  };

  return {
    temperature: nullToUndefined(defaultParams.temperature),
    topP: nullToUndefined(defaultParams.top_p),
    maxTokens: nullToUndefined(defaultParams.max_tokens),
    frequencyPenalty: nullToUndefined(defaultParams.frequency_penalty),
    presencePenalty: nullToUndefined(defaultParams.presence_penalty),
    nTimes: nullToUndefined(defaultParams.n_times) ?? 1,
    responseFormat: nullToUndefined(
      defaultParams.response_format as PlaygroundResponseFormats
    ),
    functions: nullToUndefined(defaultParams.functions),
    stopSequences: nullToUndefined(defaultParams.stop),
    messagesTemplate: nullToUndefined(defaultParams.messages_template),
  };
};
