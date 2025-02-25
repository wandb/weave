import {Box, Stack, Typography} from '@mui/material';
import React, {useEffect, useMemo} from 'react';

import {Checkbox} from '../../../../Checkbox';
import {TextField} from '../../../../Form/TextField';
import {Icon} from '../../../../Icon';
import {DataPreviewTooltip} from './DataPreviewTooltip';
import {useDatasetEditContext} from './DatasetEditorContext';
import {CallData, extractSourceSchema} from './schemaUtils';

const typographyStyle = {fontFamily: 'Source Sans Pro'};

export interface FieldConfig {
  sourceField: string;
  targetField: string;
  included: boolean;
}

interface NewDatasetSchemaStepProps {
  selectedCalls: CallData[];
  fieldConfigs: FieldConfig[];
  onFieldConfigsChange: (configs: FieldConfig[]) => void;
}

export const NewDatasetSchemaStep: React.FC<NewDatasetSchemaStepProps> = ({
  selectedCalls,
  fieldConfigs,
  onFieldConfigsChange,
}) => {
  const {resetEditState} = useDatasetEditContext();
  const sourceSchema = useMemo(() => {
    return selectedCalls.length > 0 ? extractSourceSchema(selectedCalls) : [];
  }, [selectedCalls]);

  const allFieldsIncluded = useMemo(() => {
    return (
      fieldConfigs.length > 0 && fieldConfigs.every(config => config.included)
    );
  }, [fieldConfigs]);

  const someFieldsIncluded = useMemo(() => {
    return fieldConfigs.some(config => config.included);
  }, [fieldConfigs]);

  const handleToggleAll = () => {
    const newIncluded = !someFieldsIncluded;
    const newConfigs = fieldConfigs.map(config => ({
      ...config,
      included: newIncluded,
    }));
    onFieldConfigsChange(newConfigs);
    resetEditState();
  };

  // Initialize field configs when source schema changes
  useEffect(() => {
    if (sourceSchema.length > 0 && fieldConfigs.length === 0) {
      const initialConfigs = sourceSchema.map(field => ({
        sourceField: field.name,
        targetField: field.name.replace(/^(inputs\.|output\.)/, ''),
        included: true,
      }));
      onFieldConfigsChange(initialConfigs);
    }
  }, [sourceSchema, fieldConfigs.length, onFieldConfigsChange]);

  // Extract preview data for each source field
  const fieldPreviews = useMemo(() => {
    const previews = new Map<string, Array<Record<string, any>>>();

    const getNestedValue = (obj: any, path: string[]): any => {
      let current = obj;
      for (const part of path) {
        if (current == null) {
          return undefined;
        }
        if (typeof current === 'object' && '__val__' in current) {
          current = current.__val__;
        }
        if (typeof current !== 'object') {
          return current;
        }
        current = current[part];
      }
      return current;
    };

    sourceSchema.forEach(field => {
      const fieldData = selectedCalls.map(call => {
        let value: any;
        if (field.name.startsWith('inputs.')) {
          const path = field.name.slice(7).split('.');
          value = getNestedValue(call.val.inputs, path);
        } else if (field.name.startsWith('output.')) {
          if (typeof call.val.output === 'object' && call.val.output !== null) {
            const path = field.name.slice(7).split('.');
            value = getNestedValue(call.val.output, path);
          } else {
            value = call.val.output;
          }
        } else {
          const path = field.name.split('.');
          value = getNestedValue(call.val, path);
        }
        return {[field.name]: value};
      });
      previews.set(field.name, fieldData);
    });
    return previews;
  }, [sourceSchema, selectedCalls]);

  const handleTargetFieldChange = (
    sourceField: string,
    newTargetField: string
  ) => {
    const newConfigs = fieldConfigs.map(config =>
      config.sourceField === sourceField
        ? {...config, targetField: newTargetField}
        : config
    );
    onFieldConfigsChange(newConfigs);
  };

  const handleIncludedChange = (sourceField: string) => {
    const newConfigs = fieldConfigs.map(config =>
      config.sourceField === sourceField
        ? {...config, included: !config.included}
        : config
    );
    onFieldConfigsChange(newConfigs);
    resetEditState();
  };

  if (!selectedCalls.length) {
    return (
      <Stack spacing={1} sx={{mt: 2}}>
        <Typography sx={typographyStyle}>
          No data available to extract schema from.
        </Typography>
      </Stack>
    );
  }

  if (!sourceSchema.length) {
    return (
      <Stack spacing={1} sx={{mt: 2}}>
        <Typography sx={typographyStyle}>
          No schema could be extracted from the data.
        </Typography>
      </Stack>
    );
  }

  return (
    <Stack spacing={'8px'} sx={{mt: '24px'}}>
      <Typography sx={{...typographyStyle, fontWeight: 600}}>
        Configure dataset fields
      </Typography>
      <Typography
        sx={{
          ...typographyStyle,
          color: 'text.secondary',
          fontSize: '0.875rem',
        }}>
        Select which fields from your calls to include in the dataset. For each
        included field, you can customize the column name that will appear in
        the resulting dataset.
      </Typography>
      <Box
        sx={{
          bgcolor: '#F8F8F8',
          border: '1px solid #E0E0E0',
          p: 2,
          borderRadius: 1,
        }}>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr 40px 1fr',
            gap: 2,
            mb: 2,
          }}>
          <Typography
            sx={{
              ...typographyStyle,
              color: 'text.secondary',
              fontSize: '0.875rem',
              pl: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              cursor: 'pointer',
              userSelect: 'none',
            }}
            onClick={handleToggleAll}>
            <Checkbox
              checked={
                !allFieldsIncluded && someFieldsIncluded
                  ? 'indeterminate'
                  : allFieldsIncluded
              }
              onCheckedChange={handleToggleAll}
              size="small"
            />
            Call Fields
          </Typography>
          <Box /> {/* Spacer for arrow */}
          <Typography
            sx={{
              ...typographyStyle,
              color: 'text.secondary',
              fontSize: '0.875rem',
            }}>
            Dataset Columns
          </Typography>
        </Box>
        <Stack spacing={2}>
          {fieldConfigs.map(config => (
            <Box
              key={config.sourceField}
              sx={{
                display: 'grid',
                gridTemplateColumns: '1fr 40px 1fr',
                alignItems: 'center',
                gap: 2,
              }}>
              <Box
                onClick={() => handleIncludedChange(config.sourceField)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 2,
                  cursor: 'pointer',
                  userSelect: 'none',
                  '&:hover': {
                    opacity: 0.8,
                  },
                }}>
                <Checkbox
                  checked={config.included}
                  onCheckedChange={() =>
                    handleIncludedChange(config.sourceField)
                  }
                  size="small"
                />
                <DataPreviewTooltip
                  rows={fieldPreviews.get(config.sourceField)}
                  tooltipProps={{
                    placement: 'right-start',
                    componentsProps: {
                      popper: {
                        modifiers: [
                          {
                            name: 'offset',
                            options: {
                              offset: [0, 2],
                            },
                          },
                        ],
                      },
                    },
                  }}>
                  <Typography
                    sx={{
                      ...typographyStyle,
                      color: config.included ? 'inherit' : 'text.disabled',
                    }}>
                    {config.sourceField}
                  </Typography>
                </DataPreviewTooltip>
              </Box>
              <Box sx={{display: 'flex', justifyContent: 'center'}}>
                <Icon
                  name="forward-next"
                  style={{
                    color: config.included ? 'inherit' : 'text.disabled',
                  }}
                />
              </Box>
              <Box>
                <TextField
                  value={config.targetField}
                  onChange={value =>
                    handleTargetFieldChange(config.sourceField, value)
                  }
                  placeholder="Enter field name"
                  disabled={!config.included}
                />
              </Box>
            </Box>
          ))}
        </Stack>
      </Box>
    </Stack>
  );
};
