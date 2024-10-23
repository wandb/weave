import {
  Box,
  Button,
  IconButton,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@material-ui/core';
import React from 'react';
import {z} from 'zod';

interface DynamicConfigFormProps {
  configSchema: z.ZodType<any>;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
  path?: string[];
}

export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
  configSchema,
  config,
  setConfig,
  path = [],
}) => {
  const renderField = (key: string, fieldSchema: z.ZodTypeAny) => {
    const currentPath = [...path, key];
    const currentValue = getNestedValue(config, currentPath);

    if (fieldSchema instanceof z.ZodObject) {
      return (
        <Box key={key} mb={2}>
          <Typography variant="subtitle1">{key}</Typography>
          <Box ml={2}>
            <DynamicConfigForm
              configSchema={fieldSchema}
              config={config}
              setConfig={setConfig}
              path={currentPath}
            />
          </Box>
        </Box>
      );
    }

    if (fieldSchema instanceof z.ZodArray) {
      return renderArrayField(key, fieldSchema, currentPath, currentValue);
    }

    if (fieldSchema instanceof z.ZodEnum) {
      return renderEnumField(key, fieldSchema, currentPath, currentValue);
    }

    let fieldType = 'text';
    if (fieldSchema instanceof z.ZodNumber) {
      fieldType = 'number';
    } else if (fieldSchema instanceof z.ZodBoolean) {
      fieldType = 'checkbox';
    }

    return (
      <TextField
        key={key}
        fullWidth
        label={key}
        type={fieldType}
        value={currentValue || ''}
        onChange={e => updateConfig(currentPath, e.target.value)}
        margin="normal"
      />
    );
  };

  const renderArrayField = (
    key: string,
    fieldSchema: z.ZodArray<any>,
    targetPath: string[],
    value: any[]
  ) => {
    const arrayValue = Array.isArray(value) ? value : [];
    const elementSchema = fieldSchema.element;

    return (
      <Box key={key} mb={2}>
        <Typography variant="subtitle1">{key}</Typography>
        {arrayValue.map((_, index) => (
          <Box key={index} display="flex" alignItems="center">
            <Box flexGrow={1}>
              <DynamicConfigForm
                configSchema={elementSchema}
                config={config}
                setConfig={setConfig}
                path={[...targetPath, index.toString()]}
              />
            </Box>
            <IconButton onClick={() => removeArrayItem(targetPath, index)}>
              Delete
            </IconButton>
          </Box>
        ))}
        <Button onClick={() => addArrayItem(targetPath, elementSchema)}>
          Add Item
        </Button>
      </Box>
    );
  };

  const renderEnumField = (
    key: string,
    fieldSchema: z.ZodEnum<any>,
    targetPath: string[],
    value: any
  ) => {
    const options = fieldSchema.options;

    return (
      <Box key={key} mb={2}>
        <Typography variant="subtitle1">{key}</Typography>
        <Select
          fullWidth
          value={value || ''}
          onChange={e => updateConfig(targetPath, e.target.value)}>
          {options.map(option => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </Select>
      </Box>
    );
  };

  const getNestedValue = (obj: any, targetPath: string[]): any => {
    return targetPath.reduce(
      (acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined),
      obj
    );
  };

  const updateConfig = (targetPath: string[], value: any) => {
    const newConfig = {...config};
    let current = newConfig;
    for (let i = 0; i < targetPath.length - 1; i++) {
      if (!(targetPath[i] in current)) {
        current[targetPath[i]] = {};
      }
      current = current[targetPath[i]];
    }
    current[targetPath[targetPath.length - 1]] = value;
    setConfig(newConfig);
  };

  const addArrayItem = (targetPath: string[], elementSchema: z.ZodTypeAny) => {
    const currentArray = getNestedValue(config, targetPath) || [];
    const newItem = elementSchema instanceof z.ZodObject ? {} : null;
    updateConfig(targetPath, [...currentArray, newItem]);
  };

  const removeArrayItem = (targetPath: string[], index: number) => {
    const currentArray = getNestedValue(config, targetPath) || [];
    updateConfig(
      targetPath,
      currentArray.filter((_, i) => i !== index)
    );
  };

  return (
    <>
      {path.length === 0 && (
        <Typography variant="h6" gutterBottom>
          Configuration
        </Typography>
      )}
      {Object.entries(configSchema.shape || {}).map(([key, fieldSchema]) =>
        renderField(key, fieldSchema as z.ZodTypeAny)
      )}
    </>
  );
};
