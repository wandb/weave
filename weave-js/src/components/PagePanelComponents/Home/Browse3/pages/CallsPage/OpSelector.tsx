import {Select} from '@wandb/weave/components/Form/Select';
import {SelectMultiple} from '@wandb/weave/components/Form/SelectMultiple';
import {
  ALL_TRACES_OR_CALLS_REF_KEY,
  WFHighLevelCallFilter,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {OpVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import React, {useCallback, useMemo} from 'react';

export const OpSelector = ({
  frozenFilter,
  filter,
  setFilter,
  selectedOpVersionOption,
  opVersionOptions,
  multiple = false,
  useMenuPortalBody = false,
  width,
}: {
  frozenFilter: WFHighLevelCallFilter | undefined;
  filter: WFHighLevelCallFilter;
  setFilter: (state: WFHighLevelCallFilter) => void;
  selectedOpVersionOption: string | string[];
  opVersionOptions: Record<
    string,
    {
      title: string;
      ref: string;
      group: string;
      objectVersion?: OpVersionSchema;
    }
  >;
  multiple?: boolean;
  useMenuPortalBody?: boolean;
  width?: string;
}) => {
  const frozenOpFilter = Object.keys(frozenFilter ?? {}).includes('opVersions');

  const options = useMemo(() => {
    const groupedOptions = Object.entries(opVersionOptions).reduce(
      (acc, [key, value]) => {
        const group = value.group;
        if (!acc[group]) {
          acc[group] = [];
        }
        acc[group].push({
          value: key,
          label: value.title,
        });
        return acc;
      },
      {} as Record<string, Array<{value: string; label: string}>>
    );

    return Object.entries(groupedOptions).map(([group, items]) => ({
      label: group,
      options: items,
    }));
  }, [opVersionOptions]);

  const selectedValue = useMemo(() => {
    if (multiple) {
      return Array.isArray(selectedOpVersionOption)
        ? selectedOpVersionOption.map(opt => ({
            value: opt,
            label: opVersionOptions[opt]?.title ?? opt,
          }))
        : [];
    }
    return selectedOpVersionOption &&
      typeof selectedOpVersionOption === 'string'
      ? {
          value: selectedOpVersionOption,
          label:
            opVersionOptions[selectedOpVersionOption]?.title ??
            selectedOpVersionOption,
        }
      : null;
  }, [multiple, selectedOpVersionOption, opVersionOptions]);

  const handleChange = useCallback(
    (newValue: any) => {
      if (multiple) {
        const values = newValue ? newValue.map((item: any) => item.value) : [];
        setFilter({
          ...filter,
          opVersionRefs: values,
        });
      } else {
        const value = newValue?.value;
        if (value === ALL_TRACES_OR_CALLS_REF_KEY) {
          setFilter({
            ...filter,
            opVersionRefs: [],
          });
        } else {
          setFilter({
            ...filter,
            opVersionRefs: value ? [value] : [],
          });
        }
      }
    },
    [filter, setFilter, multiple]
  );

  const SelectComponent = multiple ? SelectMultiple : Select;

  const containerStyle: React.CSSProperties = {
    minWidth: '190px',
  };

  const wrapperStyle: React.CSSProperties = width ? {width} : {width: '100%'};

  return (
    <div style={wrapperStyle}>
      <SelectComponent
        value={selectedValue}
        options={options}
        onChange={handleChange}
        isDisabled={frozenOpFilter}
        isClearable={selectedOpVersionOption !== ALL_TRACES_OR_CALLS_REF_KEY}
        size={multiple ? 'small' : 'medium'}
        placeholder="Select operation..."
        menuPortalTarget={useMenuPortalBody ? document.body : undefined}
        styles={{
          container: (base: any) => ({
            ...base,
            ...containerStyle,
          }),
          menu: (base: any) => ({
            ...base,
            zIndex: 9999,
          }),
          menuPortal: (base: any) => ({
            ...base,
            zIndex: 9999,
          }),
        }}
      />
    </div>
  );
};
