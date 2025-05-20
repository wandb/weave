import {Box} from '@mui/material';
import {
  MOON_100,
  MOON_200,
  MOON_800,
  OBLIVION,
} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import ReactDOM from 'react-dom';
import {components, OptionProps} from 'react-select';

import {LlmStructuredCompletionModel} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {
  findMaxTokensByModelName,
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';
import {
  OptionalSavedPlaygroundModelParams,
  SavedPlaygroundModelState,
} from '../types';
import {ProviderStatus} from '../useConfiguredProviders';
import {convertDefaultParamsToOptionalPlaygroundModelParams} from '../useSaveModelConfiguration';

export const SAVED_MODEL_OPTION_VALUE = 'saved-models';

export interface LLMOption {
  label: string;
  subLabel?: string | React.ReactNode;
  value: LLMMaxTokensKey | string;
  max_tokens: number;

  // Saved LLM options
  baseModelId?: LLMMaxTokensKey | null;
  defaultParams?: OptionalSavedPlaygroundModelParams;
  versionIndex?: number | null;
  isLatest?: boolean;
  objectId?: string;
}

export interface ProviderOption {
  label: string | React.ReactNode;
  value: string;
  llms: Array<LLMOption>;
  isDisabled?: boolean;
  providers?: ProviderOption[];
}

export interface CustomOptionProps extends OptionProps<ProviderOption, false> {
  onChange: (
    value: LLMMaxTokensKey,
    maxTokens: number,
    savedModel?: SavedPlaygroundModelState
  ) => void;
  entity: string;
  project: string;
  isAdmin?: boolean;
  onConfigureProvider?: (provider: string) => void;
}

const SubMenu = ({
  llms,
  onChange,
  position,
  onSelect,
  isAdmin,
  onConfigureProvider,
  providers,
}: {
  llms: Array<LLMOption>;
  onChange: (
    value: LLMMaxTokensKey,
    maxTokens: number,
    savedModel?: SavedPlaygroundModelState
  ) => void;
  position: {top: number; left: number};
  onSelect: () => void;
  isAdmin?: boolean;
  onConfigureProvider?: (provider: string) => void;
  providers?: ProviderOption[];
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
      {llms.map(llm => (
        <Box
          key={`${llm.value}${llm.versionIndex}`}
          onClick={e => {
            e.preventDefault();
            e.stopPropagation();
            onChange(
              llm.value as LLMMaxTokensKey,
              llm.max_tokens,
              llm.defaultParams && llm.baseModelId
                ? LLMOptionToSavedPlaygroundModelState(llm)
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
            <div className="text-sm text-moon-500">{llm.subLabel}</div>
          )}
        </Box>
      ))}
      {providers?.map(provider => {
        const tooltipContent =
          provider.value !== 'custom-provider' && !isAdmin
            ? 'You must be an admin to configure this provider'
            : undefined;

        const trigger = (
          <Box
            key={provider.value}
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              p: '6px',
              cursor: 'pointer',
              borderRadius: '4px',
              '&:hover': {
                backgroundColor: hexToRGB(OBLIVION, 0.04),
              },
              width: '100%',
            }}
            onClick={() => {
              if (provider.value === 'custom-provider' || isAdmin) {
                onConfigureProvider?.(provider.value);
              }
            }}>
            <Box
              sx={{
                wordBreak: 'break-all',
                wordWrap: 'break-word',
                whiteSpace: 'normal',
              }}>
              {provider.label}
            </Box>
            <Box sx={{display: 'flex', gap: 1, alignItems: 'center'}}>
              <Button
                variant="ghost"
                size="small"
                onClick={e => {
                  e.preventDefault();
                  e.stopPropagation();
                  onConfigureProvider?.(provider.value);
                }}
                disabled={!isAdmin && provider.value !== 'custom-provider'}>
                Configure
              </Button>
            </Box>
          </Box>
        );

        return tooltipContent ? (
          <Tooltip content={tooltipContent} trigger={trigger} />
        ) : (
          trigger
        );
      })}
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
  const hasOptions = llms.length > 0 || (props.data.providers?.length ?? 0) > 0;

  useEffect(() => {
    if (isHovered && optionRef.current) {
      const rect = optionRef.current.getBoundingClientRect();
      setPosition({
        top: rect.top,
        left: rect.right + 4,
      });
    }
  }, [isHovered]);

  if (props.data.value === 'divider') {
    return (
      <Box
        sx={{
          borderBottom: `1px solid ${MOON_200}`,
          my: 1,
        }}
      />
    );
  }

  return (
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
              {hasOptions && <Icon name="chevron-next" color="moon_500" />}
            </Box>
          </Box>
        </components.Option>
      </Box>
      {isHovered && hasOptions && (
        <SubMenu
          providers={props.data.providers}
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
          isAdmin={isAdmin}
          onConfigureProvider={onConfigureProvider}
        />
      )}
    </Box>
  );
};

export const CustomOption = ({
  children,
  onChange,
  entity,
  project,
  isAdmin,
  onConfigureProvider,
  data,
  ...props
}: CustomOptionProps) => {
  const {inputValue} = props.selectProps;
  // If searching, show nested structure
  if (inputValue) {
    const isDisabled = data.isDisabled;
    if (isDisabled) {
      return null;
    }

    const filteredLLMs = data.llms
      .filter(
        llm =>
          llm.value.toLowerCase().includes(inputValue.toLowerCase()) ||
          llm.label.toLowerCase().includes(inputValue.toLowerCase()) ||
          (llm.subLabel &&
            llm.subLabel
              .toString()
              .toLowerCase()
              .includes(inputValue.toLowerCase()))
      )
      .sort((a, b) => {
        return a.label.localeCompare(b.label);
      });

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
          <span>{data.label}</span>
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
              key={`${llm.value}${llm.versionIndex}`}
              onClick={() => {
                onChange(
                  llm.value as LLMMaxTokensKey,
                  llm.max_tokens,
                  llm.defaultParams && llm.baseModelId
                    ? LLMOptionToSavedPlaygroundModelState(llm)
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
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
              <div>
                {llm.label}
                {llm.subLabel && (
                  <div className="text-sm text-moon-500">{llm.subLabel}</div>
                )}
              </div>
              {llm.isLatest && <Pill label="Latest" color="moon" />}
            </Box>
          ))}
        </Box>
      </Box>
    );
  }

  const filteredData = {
    ...data,
    llms: data.llms.filter(llm => !!llm.isLatest),
  };
  // If not searching, use the hover submenu
  return (
    <SubMenuOption
      {...props}
      data={data.value === SAVED_MODEL_OPTION_VALUE ? filteredData : data}
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

export const addProviderOption = (
  disabledOptions: ProviderOption[]
): ProviderOption => ({
  label: 'Add AI provider',
  value: 'configure-provider',
  llms: [],
  providers: [
    ...disabledOptions,
    {
      label: 'Custom provider',
      value: 'custom-provider',
      llms: [],
    },
  ],
});

export const useLLMDropdownOptions = (
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

  const savedModels = useMemo(
    () =>
      // If savedModelsResult is undefined, return an empty array
      // Else convert the saved models to LLMOption(s)
      (savedModelsResult || []).map(savedModelObj => {
        const savedModelVal = savedModelObj.val as LlmStructuredCompletionModel;
        const baseModelId = savedModelVal.llm_model_id;
        const savedModelName =
          savedModelVal.name ?? savedModelObj.object_id ?? 'Unnamed Model';

        let maxTokens: number | undefined;

        // Try to determine max tokens from built-in model list
        if (baseModelId in LLM_MAX_TOKENS) {
          const baseModelConfig =
            LLM_MAX_TOKENS[baseModelId as LLMMaxTokensKey];
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
            maxTokens = customModelMatch.val.max_tokens;
          }
        }
        // Fallback max tokens determination
        if (maxTokens === undefined) {
          maxTokens = findMaxTokensByModelName(baseModelId);
        }

        const savedModelLabel = `${savedModelName}:v${savedModelObj.version_index}`;
        return {
          label: savedModelLabel,
          value: savedModelLabel,
          subLabel: baseModelId,
          baseModelId: baseModelId as LLMMaxTokensKey,
          max_tokens: maxTokens,
          defaultParams: convertDefaultParamsToOptionalPlaygroundModelParams(
            savedModelVal.default_params ?? {messages_template: []}
          ),
          objectId: savedModelName,
          versionIndex: savedModelObj.version_index ?? null,
          isLatest: !!savedModelObj.is_latest,
        };
      }),
    [savedModelsResult, customProviderModelsResult, customProvidersResult]
  );

  if (!savedModelsLoading && savedModels.length > 0) {
    savedModelsOptions.push({
      label: 'Saved Models',
      value: SAVED_MODEL_OPTION_VALUE,
      llms: savedModels,
    });
  }

  // Combine options
  // Add a divider option before the add provider option
  const allOptions = [
    ...options,
    ...savedModelsOptions,
    dividerOption,
    addProviderOption(disabledOptions),
  ];

  return allOptions;
};

export const LLMOptionToSavedPlaygroundModelState = (
  llmOption: LLMOption
): SavedPlaygroundModelState => {
  return {
    llmModelId: llmOption.baseModelId ?? null,
    objectId: llmOption.objectId ?? null,
    savedModelParams: llmOption.defaultParams ?? null,
    isLatest: llmOption.isLatest ?? false,
    versionIndex: llmOption.versionIndex ?? null,
  };
};
