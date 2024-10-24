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
import {Delete} from '@mui/icons-material';
import React, {useEffect, useMemo} from 'react';
import {z} from 'zod';

interface DynamicConfigFormProps {
  configSchema: z.ZodType<any>;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
  path?: string[];
  onValidChange?: (isValid: boolean) => void;
}

const isZodType = (
  schema: z.ZodTypeAny,
  predicate: (s: z.ZodTypeAny) => boolean
): boolean => {
  if (predicate(schema)) {
    return true;
  }
  if (schema instanceof z.ZodOptional) {
    return isZodType(schema.unwrap(), predicate);
  } else if (schema instanceof z.ZodDefault) {
    return isZodType(schema._def.innerType, predicate);
  }
  return false;
};

const unwrapSchema = (schema: z.ZodTypeAny): z.ZodTypeAny => {
  if (schema instanceof z.ZodOptional) {
    return unwrapSchema(schema.unwrap());
  } else if (schema instanceof z.ZodDefault) {
    return unwrapSchema(schema._def.innerType);
  }
  return schema;
};

const NestedForm: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
  path: string[];
}> = ({keyName, fieldSchema, config, setConfig, path}) => {
  const currentPath = [...path, keyName];
  const currentValue = getNestedValue(config, currentPath);

  const unwrappedSchema = unwrapSchema(fieldSchema);

  if (isZodType(fieldSchema, s => s instanceof z.ZodObject)) {
    return (
      <FormControl fullWidth margin="normal">
        <InputLabel>{keyName}</InputLabel>
        <Box ml={2}>
          <DynamicConfigForm
            configSchema={unwrappedSchema as z.ZodObject<any>}
            config={config}
            setConfig={setConfig}
            path={currentPath}
          />
        </Box>
      </FormControl>
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodArray)) {
    return (
      <ArrayField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodArray<any>}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodEnum)) {
    return (
      <EnumField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodEnum<any>}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodRecord)) {
    return (
      <RecordField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodRecord<any, any>}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodNumber)) {
    return (
      <NumberField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodNumber}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  let fieldType = 'text';
  if (isZodType(fieldSchema, s => s instanceof z.ZodNumber)) {
    fieldType = 'number';
  } else if (isZodType(fieldSchema, s => s instanceof z.ZodBoolean)) {
    fieldType = 'checkbox';
  }

  return (
    <TextField
      fullWidth
      label={keyName}
      type={fieldType}
      value={currentValue ?? ''}
      onChange={e =>
        updateConfig(currentPath, e.target.value, config, setConfig)
      }
      margin="normal"
    />
  );
};

const ArrayField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodArray<any>;
  targetPath: string[];
  value: any[];
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
}> = ({
  keyName,
  fieldSchema,
  unwrappedSchema,
  targetPath,
  value,
  config,
  setConfig,
}) => {
  const arrayValue = useMemo(
    () => (Array.isArray(value) ? value : []),
    [value]
  );
  const minItems = unwrappedSchema._def.minLength?.value ?? 0;

  // Ensure the minimum number of items is always present
  React.useEffect(() => {
    if (arrayValue.length < minItems) {
      const itemsToAdd = minItems - arrayValue.length;
      const newItems = Array(itemsToAdd)
        .fill(null)
        .map(() => (fieldSchema instanceof z.ZodObject ? {} : null));
      updateConfig(targetPath, [...arrayValue, ...newItems], config, setConfig);
    }
  }, [arrayValue, minItems, fieldSchema, targetPath, config, setConfig]);

  return (
    <FormControl fullWidth margin="normal">
      <InputLabel>{keyName}</InputLabel>
      {arrayValue.map((_, index) => (
        <Box
          key={index}
          display="flex"
          flexDirection="column"
          alignItems="flex-start"
          mb={2}
          sx={{
            borderBottom: '1px solid',
            p: 2,
          }}>
          <Box flexGrow={1} width="100%">
            <DynamicConfigForm
              configSchema={fieldSchema}
              config={config}
              setConfig={setConfig}
              path={[...targetPath, index.toString()]}
            />
          </Box>
          <Box mt={1}>
            <IconButton
              onClick={() =>
                removeArrayItem(targetPath, index, config, setConfig)
              }
              disabled={arrayValue.length <= minItems}>
              <Delete />
            </IconButton>
          </Box>
        </Box>
      ))}
      <Button
        onClick={() =>
          addArrayItem(targetPath, fieldSchema, config, setConfig)
        }>
        Add Item
      </Button>
    </FormControl>
  );
};

const EnumField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodEnum<any>;
  targetPath: string[];
  value: any;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
}> = ({
  keyName,
  fieldSchema,
  unwrappedSchema,
  targetPath,
  value,
  config,
  setConfig,
}) => {
  const options = unwrappedSchema.options;

  const selectedValue = value ?? options[0];
  useEffect(() => {
    if (value === null || value === undefined) {
      updateConfig(targetPath, selectedValue, config, setConfig);
    }
  }, [value, selectedValue, targetPath, config, setConfig]);

  return (
    <FormControl fullWidth margin="normal">
      <InputLabel>{keyName}</InputLabel>
      <Select
        fullWidth
        value={selectedValue}
        onChange={e =>
          updateConfig(targetPath, e.target.value, config, setConfig)
        }>
        {options.map((option: string) => (
          <MenuItem key={option} value={option}>
            {option}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

const RecordField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodRecord<any, any>;
  targetPath: string[];
  value: Record<string, any>;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
}> = ({
  keyName,
  fieldSchema,
  unwrappedSchema,
  targetPath,
  value,
  config,
  setConfig,
}) => {
  const recordValue = value || {};

  return (
    <FormControl fullWidth margin="normal">
      <InputLabel>{keyName}</InputLabel>
      {Object.entries(recordValue).map(([recordValueKey, recordValueValue]) => (
        <Box key={recordValueKey} display="flex" alignItems="center">
          <TextField
            fullWidth
            label={`Key: ${recordValueKey}`}
            value={recordValueKey}
            onChange={e =>
              updateRecordKey(
                targetPath,
                recordValueKey,
                e.target.value,
                config,
                setConfig
              )
            }
            margin="normal"
          />
          <TextField
            fullWidth
            label={`Value: ${recordValueKey}`}
            value={recordValueValue}
            onChange={e =>
              updateRecordValue(
                targetPath,
                recordValueKey,
                e.target.value,
                config,
                setConfig
              )
            }
            margin="normal"
          />
          <IconButton
            onClick={() =>
              removeRecordItem(targetPath, recordValueKey, config, setConfig)
            }>
            <Delete />
          </IconButton>
        </Box>
      ))}
      <Button onClick={() => addRecordItem(targetPath, config, setConfig)}>
        Add Item
      </Button>
    </FormControl>
  );
};

const getNestedValue = (obj: any, targetPath: string[]): any => {
  return targetPath.reduce(
    (acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined),
    obj
  );
};

const updateConfig = (
  targetPath: string[],
  value: any,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
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

const addArrayItem = (
  targetPath: string[],
  elementSchema: z.ZodTypeAny,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentArray = getNestedValue(config, targetPath) || [];
  const newItem = elementSchema instanceof z.ZodObject ? {} : null;
  updateConfig(targetPath, [...currentArray, newItem], config, setConfig);
};

const removeArrayItem = (
  targetPath: string[],
  index: number,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentArray = getNestedValue(config, targetPath) || [];
  const fieldSchema = getNestedValue(config, targetPath.slice(0, -1));
  const minItems = fieldSchema?._def?.minLength?.value ?? 0;

  if (currentArray.length > minItems) {
    updateConfig(
      targetPath,
      currentArray.filter((_: any, i: number) => i !== index),
      config,
      setConfig
    );
  }
};

const addRecordItem = (
  targetPath: string[],
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentRecord = getNestedValue(config, targetPath) || {};
  const newKey = `key${Object.keys(currentRecord).length + 1}`;
  updateConfig(targetPath, {...currentRecord, [newKey]: ''}, config, setConfig);
};

const removeRecordItem = (
  targetPath: string[],
  key: string,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentRecord = getNestedValue(config, targetPath) || {};
  const {[key]: _, ...newRecord} = currentRecord;
  updateConfig(targetPath, newRecord, config, setConfig);
};

const updateRecordKey = (
  targetPath: string[],
  oldKey: string,
  newKey: string,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentRecord = getNestedValue(config, targetPath) || {};
  const {[oldKey]: value, ...rest} = currentRecord;
  updateConfig(targetPath, {...rest, [newKey]: value}, config, setConfig);
};

const updateRecordValue = (
  targetPath: string[],
  key: string,
  value: any,
  config: Record<string, any>,
  setConfig: (config: Record<string, any>) => void
) => {
  const currentRecord = getNestedValue(config, targetPath) || {};
  updateConfig(targetPath, {...currentRecord, [key]: value}, config, setConfig);
};

const validateConfig = (schema: z.ZodType<any>, config: any): boolean => {
  try {
    schema.parse(config);
    return true;
  } catch (error) {
    return false;
  }
};

const NumberField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodNumber;
  targetPath: string[];
  value: number | undefined;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
}> = ({
  keyName,
  fieldSchema,
  unwrappedSchema,
  targetPath,
  value,
  config,
  setConfig,
}) => {
  const min =
    (unwrappedSchema._def.checks.find(check => check.kind === 'min') as any)
      ?.value ?? undefined;
  const max =
    (unwrappedSchema._def.checks.find(check => check.kind === 'max') as any)
      ?.value ?? undefined;
  // const defaultValue =
  //   fieldSchema instanceof z.ZodDefault
  //     ? fieldSchema._def.defaultValue()
  //     : undefined;

  // useEffect(() => {
  //   if (value === undefined && defaultValue !== undefined) {
  //     updateConfig(targetPath, defaultValue, config, setConfig);
  //   }
  // }, [value, defaultValue, targetPath, config, setConfig]);

  return (
    <TextField
      fullWidth
      label={keyName}
      type="number"
      value={value ?? ''}
      onChange={e => {
        const newValue =
          e.target.value === '' ? undefined : Number(e.target.value);
        if (newValue !== undefined && (newValue < min || newValue > max)) {
          return;
        }
        updateConfig(targetPath, newValue, config, setConfig);
      }}
      inputProps={{min, max}}
      margin="normal"
    />
  );
};

export const DynamicConfigForm: React.FC<DynamicConfigFormProps> = ({
  configSchema,
  config,
  setConfig,
  path = [],
  onValidChange,
}) => {
  useEffect(() => {
    const validationResult = validateConfig(configSchema, config);
    if (onValidChange) {
      onValidChange(validationResult);
    }
  }, [config, configSchema, onValidChange]);

  const renderContent = () => {
    if (configSchema instanceof z.ZodRecord) {
      return (
        <RecordField
          keyName=""
          fieldSchema={configSchema}
          unwrappedSchema={configSchema}
          targetPath={[]}
          value={config}
          config={config}
          setConfig={setConfig}
        />
      );
    } else if (configSchema instanceof z.ZodObject) {
      return Object.entries(configSchema.shape).map(([key, fieldSchema]) => (
        <NestedForm
          key={key} // React key for list rendering
          keyName={key}
          fieldSchema={fieldSchema as z.ZodTypeAny}
          config={config}
          setConfig={setConfig}
          path={path}
        />
      ));
    } else {
      return <Typography color="error">Unsupported schema type</Typography>;
    }
  };

  return <>{renderContent()}</>;
};
