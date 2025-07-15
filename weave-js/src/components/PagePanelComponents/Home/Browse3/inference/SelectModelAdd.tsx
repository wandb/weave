/**
 * Select the grid column that a filter applies to.
 */
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';
import {components, OptionProps, SingleValueProps} from 'react-select';

import {
  LLM_PROVIDER_LABELS,
  LLM_PROVIDERS,
} from '../pages/PlaygroundPage/llmMaxTokens';
import {ModelTile} from './ModelTile';
import {Model, ModelInfo} from './types';

type ModelOption = {
  readonly value: string;
  readonly label: string;
  readonly model: Model;
};

export type GroupedOption = {
  readonly label: string;
  readonly options: ModelOption[];
  readonly provider: string;
};

export type SelectModelAddOption = ModelOption | GroupedOption;

type SelectModelAddProps = {
  modelInfo: ModelInfo;
  value: string;
  isDisabled?: boolean;
  onSelectModelAdd: (id: string) => void;
  alreadySelected: string[];
};

const Option = (props: OptionProps<ModelOption, false, GroupedOption>) => {
  const {data} = props;
  const {model} = data;

  return (
    <components.Option {...props}>
      <div className="flex w-full items-center justify-between">
        <div className="flex-1">
          <div className="whitespace-nowrap text-left font-medium">
            {data.label}
          </div>
        </div>
        <div className="ml-2 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            icon="info"
            variant="ghost"
            size="small"
            tooltip={
              <ModelTile
                model={model}
                hint="Click info button for full model details"
              />
            }
            tooltipProps={{
              className: 'p-0 bg-transparent',
              side: 'bottom',
              sideOffset: 8,
            }}
            onClick={e => {
              e.stopPropagation();
            }}
          />
        </div>
      </div>
    </components.Option>
  );
};

const OptionLabel = (props: SelectModelAddOption) => {
  const {label} = props;
  return <span className="whitespace-nowrap">{label}</span>;
};

// What is shown in the input field when a value is selected.
const SingleValue = ({
  children,
  ...props
}: SingleValueProps<ModelOption, false, GroupedOption>) => {
  return <components.SingleValue {...props}>{children}</components.SingleValue>;
};

const modelToModelOption = (model: Model) => {
  return {
    value: model.id,
    label: model.label ?? model.idHuggingFace?.split('/').pop() ?? model.id,
    model,
  };
};

export const SelectModelAdd = ({
  modelInfo,
  value,
  isDisabled,
  onSelectModelAdd,
  alreadySelected,
}: SelectModelAddProps) => {
  // Group models by provider

  console.log({LLM_PROVIDERS});

  const groupedOptions = [];

  for (const provider of LLM_PROVIDERS) {
    const models = modelInfo.models
      .filter(model => model.provider === provider)
      .map(modelToModelOption);
    console.log({provider, models});
    groupedOptions.push({
      label: LLM_PROVIDER_LABELS[provider] ?? '',
      provider,
      options: models,
    });
  }

  let isDisabledOverride = isDisabled ?? false;
  let selectedOption = groupedOptions
    .flatMap(group => group.options)
    .find(o => o.value === value);

  // Handle the case of a filter that we let the user create but not edit.
  if (value && !selectedOption) {
    isDisabledOverride = true;
    const model = modelInfo.models.find(m => m.id === value);
    if (model) {
      selectedOption = {
        value,
        label: model.label ?? model.idHuggingFace?.split('/').pop() ?? model.id,
        model,
      };
    }
  }

  const onReactSelectChange = (option: ModelOption | null) => {
    if (option) {
      onSelectModelAdd(option.value);
    }
  };

  return (
    <Select<ModelOption, false, GroupedOption>
      options={groupedOptions}
      placeholder="Select model"
      value={selectedOption}
      onChange={onReactSelectChange}
      components={{Option, SingleValue}}
      formatOptionLabel={OptionLabel}
      isDisabled={isDisabledOverride}
      autoFocus
      isSearchable
      filterOption={(option, inputValue) => {
        const searchTerm = inputValue.toLowerCase();
        const label =
          typeof option.data?.label === 'string' ? option.data.label : '';

        // Check if this is a grouped option with nested options
        if ('options' in option.data && Array.isArray(option.data.options)) {
          return (
            label.toLowerCase().includes(searchTerm) ||
            option.data.options.some((modelOption: ModelOption) =>
              modelOption.label.toLowerCase().includes(searchTerm)
            )
          );
        }

        // For individual model options
        return label.toLowerCase().includes(searchTerm);
      }}
      isOptionDisabled={option => alreadySelected.includes(option.value)}
    />
  );
};
