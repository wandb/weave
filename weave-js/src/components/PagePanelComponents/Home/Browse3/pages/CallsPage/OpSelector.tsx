import {
  Autocomplete as MuiAutocomplete,
  FormControl,
  ListItem,
  SxProps,
} from '@mui/material';
import {MOON_200, TEAL_300} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import {
  ALL_TRACES_OR_CALLS_REF_KEY,
  WFHighLevelCallFilter,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {OpVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {StyledPaper} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/StyledAutocomplete';
import {StyledTextField} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/StyledTextField';
import React, {useCallback} from 'react';

export const OpSelector = ({
  frozenFilter,
  filter,
  setFilter,
  selectedOpVersionOption,
  opVersionOptions,
  multiple = false,
  sx,
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
  sx?: SxProps;
}) => {
  const frozenOpFilter = Object.keys(frozenFilter ?? {}).includes('opVersions');
  const handleChange = useCallback(
    (event: any, newValue: string | string[] | null) => {
      if (newValue === ALL_TRACES_OR_CALLS_REF_KEY) {
        setFilter({
          ...filter,
          opVersionRefs: [],
        });
      } else {
        setFilter({
          ...filter,
          opVersionRefs: newValue
            ? Array.isArray(newValue)
              ? newValue
              : [newValue]
            : [],
        });
      }
    },
    [filter, setFilter]
  );

  return (
    <Autocomplete
      multiple={multiple}
      sx={sx}
      disabled={frozenOpFilter}
      value={selectedOpVersionOption}
      onChange={handleChange}
      getOptionLabel={option => opVersionOptions[option]?.title ?? ''}
      disableClearable={selectedOpVersionOption === ALL_TRACES_OR_CALLS_REF_KEY}
      groupBy={option => opVersionOptions[option]?.group}
      options={Object.keys(opVersionOptions)}
    />
  );
};

type AutocompleteProps = {
  multiple?: boolean;
  sx?: SxProps;
  disabled?: boolean;
  value: string | string[];
  onChange: (event: any, newValue: string | string[] | null) => void;
  getOptionLabel?: (option: any) => string;
  disableClearable?: boolean;
  groupBy?: (option: any) => string;
  options: string[];
};

export const Autocomplete = (props: AutocompleteProps) => {
  return (
    <div className="flex-none">
      <ListItem
        sx={{
          minWidth: '190px',
          width: '320px',
          height: '32px',
          padding: '0px',
          ...(props.sx as any),
        }}>
        <FormControl fullWidth sx={{borderColor: MOON_200, width: '100%'}}>
          <MuiAutocomplete
            PaperComponent={paperProps => <StyledPaper {...paperProps} />}
            ListboxProps={{
              sx: {
                fontSize: '14px',
                fontFamily: 'Source Sans Pro',
                '& .MuiAutocomplete-option': {
                  fontSize: '14px',
                  fontFamily: 'Source Sans Pro',
                },
                '& .MuiAutocomplete-groupLabel': {
                  fontSize: '14px',
                  fontFamily: 'Source Sans Pro',
                },
              },
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                height: props.multiple ? 'auto' : '32px',
                fontFamily: 'Source Sans Pro',
                '& fieldset': {
                  borderColor: MOON_200,
                },
                '&:hover fieldset': {
                  borderColor: `rgba(${TEAL_300}, 0.48)`,
                },
              },
              '& .MuiOutlinedInput-input': {
                fontSize: '14px',
                height: '32px',
                padding: '0 14px',
                boxSizing: 'border-box',
                fontFamily: 'Source Sans Pro',
              },
              '& .MuiAutocomplete-clearIndicator, & .MuiAutocomplete-popupIndicator':
                {
                  backgroundColor: 'transparent',
                  marginBottom: '2px',
                },
            }}
            size="small"
            renderInput={renderParams => <StyledTextField {...renderParams} />}
            popupIcon={<Icon name="chevron-down" width={16} height={16} />}
            clearIcon={<Icon name="close" width={16} height={16} />}
            {...props}
          />
        </FormControl>
      </ListItem>
    </div>
  );
};
