import {
  Box,
  Button,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@material-ui/core';
import { Delete } from '@mui/icons-material';
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
        <FormControl fullWidth margin="normal">
          <InputLabel>{key}</InputLabel>
          <Box ml={2}>
            <DynamicConfigForm
              configSchema={fieldSchema}
              config={config}
              setConfig={setConfig}
              path={currentPath}
            />
          </Box>
        </FormControl>
      );
    }

    if (fieldSchema instanceof z.ZodArray) {
      return renderArrayField(key, fieldSchema, currentPath, currentValue);
    }

    if (fieldSchema instanceof z.ZodEnum) {
      return renderEnumField(key, fieldSchema, currentPath, currentValue);
    }

    if (fieldSchema instanceof z.ZodRecord) {
      return renderRecordField(key, fieldSchema, currentPath, currentValue);
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
      <FormControl fullWidth margin="normal">
        <InputLabel>{key}</InputLabel>
        {arrayValue.map((_, index) => (
          <Box key={index} display="flex" flexDirection="column" alignItems="flex-start" mb={2} sx={{
            borderBottom: '1px solid',
            p: 2,
          }}>
            <Box flexGrow={1} width="100%">
              <DynamicConfigForm
                configSchema={elementSchema}
                config={config}
                setConfig={setConfig}
                path={[...targetPath, index.toString()]}
              />
            </Box>
            <Box mt={1}>
              <IconButton onClick={() => removeArrayItem(targetPath, index)}>
                <Delete />
              </IconButton>
            </Box>
          </Box>
        ))}
        <Button onClick={() => addArrayItem(targetPath, elementSchema)}>
          Add Item
        </Button>
      </FormControl>
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
      <FormControl fullWidth margin="normal">
        <InputLabel>{key}</InputLabel>
        <Select
          fullWidth
          value={value || ''}
          onChange={e => updateConfig(targetPath, e.target.value)}>
          {options.map((option: string) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    );
  };

  const renderRecordField = (
    key: string,
    fieldSchema: z.ZodRecord<any, any>,
    targetPath: string[],
    value: Record<string, any>
  ) => {
    const recordValue = value || {};

    return (
      <FormControl fullWidth margin="normal">
        <InputLabel>{key}</InputLabel>
        {Object.entries(recordValue).map(
          ([recordValueKey, recordValueValue]) => (
            <Box key={recordValueKey} display="flex" alignItems="center">
              <TextField
                fullWidth
                label={`Key: ${recordValueKey}`}
                value={recordValueKey}
                onChange={e =>
                  updateRecordKey(targetPath, recordValueKey, e.target.value)
                }
                margin="normal"
              />
              <TextField
                fullWidth
                label={`Value: ${recordValueKey}`}
                value={recordValueValue}
                onChange={e =>
                  updateRecordValue(targetPath, recordValueKey, e.target.value)
                }
                margin="normal"
              />
              <IconButton
                onClick={() => removeRecordItem(targetPath, recordValueKey)}>
                Delete
              </IconButton>
            </Box>
          )
        )}
        <Button onClick={() => addRecordItem(targetPath)}>Add Item</Button>
      </FormControl>
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
      currentArray.filter((_: any, i: number) => i !== index)
    );
  };

  const addRecordItem = (targetPath: string[]) => {
    const currentRecord = getNestedValue(config, targetPath) || {};
    const newKey = `key${Object.keys(currentRecord).length + 1}`;
    updateConfig(targetPath, {...currentRecord, [newKey]: ''});
  };

  const removeRecordItem = (targetPath: string[], key: string) => {
    const currentRecord = getNestedValue(config, targetPath) || {};
    const {[key]: _, ...newRecord} = currentRecord;
    updateConfig(targetPath, newRecord);
  };

  const updateRecordKey = (
    targetPath: string[],
    oldKey: string,
    newKey: string
  ) => {
    const currentRecord = getNestedValue(config, targetPath) || {};
    const {[oldKey]: value, ...rest} = currentRecord;
    updateConfig(targetPath, {...rest, [newKey]: value});
  };

  const updateRecordValue = (targetPath: string[], key: string, value: any) => {
    const currentRecord = getNestedValue(config, targetPath) || {};
    updateConfig(targetPath, {...currentRecord, [key]: value});
  };

  const renderContent = () => {
    if (configSchema instanceof z.ZodRecord) {
      return renderRecordField('', configSchema, [], config);
    } else if (configSchema instanceof z.ZodObject) {
      return Object.entries(configSchema.shape).map(([key, fieldSchema]) =>
        renderField(key, fieldSchema as z.ZodTypeAny)
      );
    } else {
      return <Typography color="error">Unsupported schema type</Typography>;
    }
  };

  return <>{renderContent()}</>
};
