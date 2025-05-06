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
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useRef, useState} from 'react';
import ReactDOM from 'react-dom';
import {components, OptionProps} from 'react-select';

import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';
import {ProviderStatus} from '../useConfiguredProviders';

export interface LLMOption {
  label: string;
  value: LLMMaxTokensKey;
  max_tokens: number;
  provider?: string;
}
export interface ProviderOption {
  label: string | React.ReactNode;
  value: string;
  llms: Array<LLMOption>;
  isDisabled?: boolean;
  providers?: ProviderOption[];
}

export interface CustomOptionProps extends OptionProps<ProviderOption, false> {
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
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
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
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
          key={llm.value}
          onClick={e => {
            e.preventDefault();
            e.stopPropagation();
            onChange(llm.value, llm.max_tokens);
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
  ...props
}: CustomOptionProps) => {
  const {inputValue} = props.selectProps;
  // If searching, show nested structure
  if (inputValue) {
    const {llms, isDisabled} = props.data;
    if (isDisabled) {
      return null;
    }

    const filteredLLMs = llms.filter(
      llm =>
        llm.value.toLowerCase().includes(inputValue.toLowerCase()) ||
        llm.label.toLowerCase().includes(inputValue.toLowerCase())
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
                onChange(llm.value as LLMMaxTokensKey, llm.max_tokens);
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

export const getLLMDropdownOptions = (
  configuredProviders: Record<string, ProviderStatus>,
  configuredProvidersLoading: boolean,
  customProvidersResult: TraceObjSchemaForBaseObjectClass<'Provider'>[],
  customProviderModelsResult: TraceObjSchemaForBaseObjectClass<'ProviderModel'>[],
  customLoading: boolean
) => {
  const options: ProviderOption[] = [];
  const disabledOptions: ProviderOption[] = [];

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

  // Combine options
  // Add a divider option before the add provider option
  const allOptions = [
    ...options,
    dividerOption,
    addProviderOption(disabledOptions),
  ];

  return allOptions;
};
