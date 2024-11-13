import {
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Tooltip,
  Typography,
} from '@material-ui/core';
import {Delete, Help} from '@mui/icons-material';
import React, {useEffect, useMemo, useState} from 'react';
import {z} from 'zod';

import {parseRefMaybe} from '../Browse2/SmallRef';

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
  if (schema instanceof z.ZodOptional || schema instanceof z.ZodDefault) {
    return isZodType(unwrapSchema(schema), predicate);
  }
  if (schema instanceof z.ZodDiscriminatedUnion) {
    return true;
  }
  return false;
};

const unwrapSchema = (schema: z.ZodTypeAny): z.ZodTypeAny => {
  if (schema instanceof z.ZodOptional || schema instanceof z.ZodDefault) {
    return unwrapSchema(schema._def.innerType);
  }
  if (schema instanceof z.ZodDiscriminatedUnion) {
    return schema;
  }
  return schema;
};

const DiscriminatedUnionField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodDiscriminatedUnion<
    string,
    Array<z.ZodObject<any, any, any>>
  >;
  targetPath: string[];
  value: any;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
}> = ({keyName, fieldSchema, targetPath, value, config, setConfig}) => {
  const discriminator = fieldSchema._def.discriminator;
  const options = fieldSchema._def.options;

  const currentType =
    value?.[discriminator] || options[0]._def.shape()[discriminator]._def.value;

  const handleTypeChange = (newType: string) => {
    const selectedOption = options.find(
      option => option._def.shape()[discriminator]._def.value === newType
    );
    if (selectedOption) {
      const newValue = {[discriminator]: newType};
      Object.keys(selectedOption.shape).forEach(key => {
        if (key !== discriminator) {
          newValue[key] =
            selectedOption.shape[key] instanceof z.ZodDefault
              ? selectedOption.shape[key]._def.defaultValue()
              : undefined;
        }
      });
      updateConfig(targetPath, newValue, config, setConfig);
    }
  };

  const selectedSchema = options.find(
    option => option._def.shape()[discriminator]._def.value === currentType
  )!;

  // Create a new schema without the discriminator field
  const filteredSchema = z.object(
    Object.entries(selectedSchema.shape).reduce((acc, [key, innerValue]) => {
      if (key !== discriminator) {
        acc[key] = innerValue as z.ZodTypeAny;
      }
      return acc;
    }, {} as Record<string, z.ZodTypeAny>)
  );

  return (
    <FormControl fullWidth margin="dense">
      <InputLabel>{keyName}</InputLabel>
      <Select
        value={currentType}
        onChange={e => handleTypeChange(e.target.value as string)}
        fullWidth>
        {options.map(option => (
          <MenuItem
            key={option._def.shape()[discriminator]._def.value}
            value={option._def.shape()[discriminator]._def.value}>
            {option._def.shape()[discriminator]._def.value}
          </MenuItem>
        ))}
      </Select>
      <Box mt={2}>
        <DynamicConfigForm
          configSchema={filteredSchema}
          config={value || {}}
          setConfig={newConfig => {
            const updatedConfig = {...newConfig, [discriminator]: currentType};
            updateConfig(targetPath, updatedConfig, config, setConfig);
          }}
          path={[]}
        />
      </Box>
    </FormControl>
  );
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

  if (unwrappedSchema instanceof z.ZodDiscriminatedUnion) {
    return (
      <DiscriminatedUnionField
        keyName={keyName}
        fieldSchema={unwrappedSchema}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodObject)) {
    return (
      <FormControl fullWidth margin="dense">
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

  if (isZodType(fieldSchema, s => s instanceof z.ZodLiteral)) {
    return (
      <LiteralField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodLiteral<any>}
        targetPath={currentPath}
        value={currentValue}
        config={config}
        setConfig={setConfig}
      />
    );
  }

  if (isZodType(fieldSchema, s => s instanceof z.ZodBoolean)) {
    return (
      <BooleanField
        keyName={keyName}
        fieldSchema={fieldSchema}
        unwrappedSchema={unwrappedSchema as z.ZodBoolean}
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
    <Box display="flex" alignItems="center" width="100%">
      <TextField
        fullWidth
        label={keyName}
        type={fieldType}
        value={currentValue ?? ''}
        onChange={e =>
          updateConfig(currentPath, e.target.value, config, setConfig)
        }
        margin="dense"
      />
      <DescriptionTooltip description={getFieldDescription(fieldSchema)} />
    </Box>
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
  const elementSchema = unwrappedSchema.element;

  // Ensure the minimum number of items is always present
  React.useEffect(() => {
    if (arrayValue.length < minItems) {
      const itemsToAdd = minItems - arrayValue.length;
      const newItems = Array(itemsToAdd)
        .fill(null)
        .map(() => (elementSchema instanceof z.ZodObject ? {} : null));
      updateConfig(targetPath, [...arrayValue, ...newItems], config, setConfig);
    }
  }, [arrayValue, minItems, elementSchema, targetPath, config, setConfig]);

  return (
    <FormControl fullWidth margin="dense">
      <InputLabel>{keyName}</InputLabel>
      {arrayValue.map((item, index) => (
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
            <NestedForm
              keyName={`${index}`}
              fieldSchema={elementSchema}
              config={{[`${index}`]: item}}
              setConfig={newItemConfig => {
                const newArray = [...arrayValue];
                newArray[index] = newItemConfig[`${index}`];
                updateConfig(targetPath, newArray, config, setConfig);
              }}
              path={[]}
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
          addArrayItem(targetPath, elementSchema, config, setConfig)
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

  // Determine the default value
  const defaultValue = React.useMemo(() => {
    if (fieldSchema instanceof z.ZodDefault) {
      return fieldSchema._def.defaultValue();
    }
    if (options.length > 0) {
      return options[0];
    }
    return undefined;
  }, [fieldSchema, options]);
  // Use the default value if the current value is null or undefined
  const selectedValue = value ?? defaultValue;

  useEffect(() => {
    if (value === null || value === undefined) {
      updateConfig(targetPath, selectedValue, config, setConfig);
    }
  }, [value, selectedValue, targetPath, config, setConfig]);

  return (
    <FormControl fullWidth margin="dense">
      <Box display="flex" alignItems="center">
        {keyName !== '' ? (
          <InputLabel>{keyName}</InputLabel>
        ) : (
          <div style={{height: '1px'}} />
        )}
        <DescriptionTooltip description={getFieldDescription(fieldSchema)} />
      </Box>
      <Select
        fullWidth
        value={selectedValue}
        onChange={e =>
          updateConfig(targetPath, e.target.value, config, setConfig)
        }>
        {options.map((option: string) => {
          let displayValue = option;
          const ref = parseRefMaybe(displayValue);
          if (ref) {
            displayValue = `${ref.artifactName} [${ref.artifactVersion.slice(
              0,
              8
            )}]`;
          }
          return (
            <MenuItem key={option} value={option}>
              {displayValue}
            </MenuItem>
          );
        })}
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
  const [internalPairs, setInternalPairs] = useState<
    Array<{key: string; value: any}>
  >([]);

  const valueSchema = unwrappedSchema._def.valueType;
  const unwrappedValueSchema = unwrapSchema(valueSchema);

  // Initialize or update internalPairs when value changes
  useEffect(() => {
    if (value && typeof value === 'object') {
      setInternalPairs(
        Object.entries(value).map(([key, val]) => ({key, value: val}))
      );
    } else {
      setInternalPairs([]);
    }
  }, [value]);

  const updateInternalPair = (index: number, newKey: string, newValue: any) => {
    const newPairs = [...internalPairs];
    newPairs[index] = {key: newKey, value: newValue};
    setInternalPairs(newPairs);

    // Update the actual config
    const newRecord = newPairs.reduce((acc, {key, value: innerValue}) => {
      acc[key] = innerValue;
      return acc;
    }, {} as Record<string, any>);
    updateConfig(targetPath, newRecord, config, setConfig);
  };

  const addNewPair = () => {
    const newKey = `key${internalPairs.length + 1}`;
    let defaultValue: any = '';
    if (valueSchema instanceof z.ZodDefault) {
      defaultValue = valueSchema._def.defaultValue();
    } else if (valueSchema instanceof z.ZodEnum) {
      defaultValue = valueSchema.options[0];
    } else if (valueSchema instanceof z.ZodBoolean) {
      defaultValue = false;
    } else if (valueSchema instanceof z.ZodNumber) {
      defaultValue = 0;
    }
    setInternalPairs([...internalPairs, {key: newKey, value: defaultValue}]);
    updateConfig(
      targetPath,
      {...value, [newKey]: defaultValue},
      config,
      setConfig
    );
  };

  const removePair = (index: number) => {
    const newPairs = internalPairs.filter((_, i) => i !== index);
    setInternalPairs(newPairs);

    const newRecord = newPairs.reduce((acc, {key, value: innerValue}) => {
      acc[key] = innerValue;
      return acc;
    }, {} as Record<string, any>);
    updateConfig(targetPath, newRecord, config, setConfig);
  };

  return (
    <FormControl fullWidth margin="dense">
      <InputLabel>{keyName}</InputLabel>
      {internalPairs.map(({key, value: innerValue}, index) => (
        <Box key={index} display="flex" alignItems="center">
          <TextField
            fullWidth
            value={key}
            onChange={e => {
              if (
                internalPairs.some(
                  (pair, i) => i !== index && pair.key === e.target.value
                )
              ) {
                // Prevent duplicate keys
                return;
              }
              updateInternalPair(index, e.target.value, innerValue);
            }}
            margin="dense"
          />
          {isZodType(valueSchema, s => s instanceof z.ZodEnum) ? (
            <EnumField
              keyName={``}
              fieldSchema={valueSchema}
              unwrappedSchema={unwrappedValueSchema as z.ZodEnum<any>}
              targetPath={[...targetPath, key]}
              value={innerValue}
              config={config}
              setConfig={newConfig => {
                const newValue = getNestedValue(newConfig, [
                  ...targetPath,
                  key,
                ]);
                updateInternalPair(index, key, newValue);
              }}
            />
          ) : (
            <TextField
              fullWidth
              value={innerValue}
              onChange={e => updateInternalPair(index, key, e.target.value)}
              margin="dense"
            />
          )}
          <IconButton onClick={() => removePair(index)}>
            <Delete />
          </IconButton>
        </Box>
      ))}
      <Button onClick={addNewPair}>Add Item</Button>
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

  // Convert OrderedRecord to plain object if necessary
  if (
    value &&
    typeof value === 'object' &&
    'keys' in value &&
    'values' in value
  ) {
    const plainObject: Record<string, any> = {};
    value.keys.forEach((key: string) => {
      plainObject[key] = value.values[key];
    });
    current[targetPath[targetPath.length - 1]] = plainObject;
  } else {
    current[targetPath[targetPath.length - 1]] = value;
  }

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
  const unwrappedSchema = unwrapSchema(
    getNestedValue(config, targetPath.slice(0, -1))
  );
  const minItems =
    unwrappedSchema instanceof z.ZodArray
      ? unwrappedSchema._def.minLength?.value ?? 0
      : 0;

  if (currentArray.length > minItems) {
    updateConfig(
      targetPath,
      currentArray.filter((_: any, i: number) => i !== index),
      config,
      setConfig
    );
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
    <Box display="flex" alignItems="center" width="100%">
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
        margin="dense"
      />
      <DescriptionTooltip description={getFieldDescription(fieldSchema)} />
    </Box>
  );
};

const LiteralField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodLiteral<any>;
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
  const literalValue = unwrappedSchema.value;

  useEffect(() => {
    if (value !== literalValue) {
      updateConfig(targetPath, literalValue, config, setConfig);
    }
  }, [value, literalValue, targetPath, config, setConfig]);

  return (
    <TextField
      fullWidth
      label={keyName}
      value={literalValue}
      InputProps={{
        readOnly: true,
      }}
      margin="dense"
      variant="filled"
    />
  );
};

const BooleanField: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  unwrappedSchema: z.ZodBoolean;
  targetPath: string[];
  value: boolean | undefined;
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
  const defaultValue =
    fieldSchema instanceof z.ZodDefault
      ? fieldSchema._def.defaultValue()
      : false;

  useEffect(() => {
    if (value === undefined) {
      updateConfig(targetPath, defaultValue, config, setConfig);
    }
  }, [value, defaultValue, targetPath, config, setConfig]);

  return (
    <Box display="flex" alignItems="center">
      <FormControlLabel
        control={
          <Checkbox
            checked={value ?? defaultValue}
            onChange={e =>
              updateConfig(targetPath, e.target.checked, config, setConfig)
            }
          />
        }
        label={keyName}
      />
      <DescriptionTooltip description={getFieldDescription(fieldSchema)} />
    </Box>
  );
};

const getFieldDescription = (schema: z.ZodTypeAny): string | undefined => {
  if ('description' in schema._def) {
    return schema._def.description;
  }
  if (schema instanceof z.ZodOptional || schema instanceof z.ZodDefault) {
    return getFieldDescription(schema._def.innerType);
  }
  return undefined;
};

const DescriptionTooltip: React.FC<{description?: string}> = ({description}) => {
  if (!description) {
    return null;
  }
  return (
    <Tooltip title={description}>
      <IconButton size="small">
        <Help fontSize="small" />
      </IconButton>
    </Tooltip>
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
    const validationResult = configSchema.safeParse(config);
    if (onValidChange) {
      onValidChange(validationResult.success);
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
      console.error('Unsupported schema type', configSchema);
      return <Typography color="error">Unsupported schema type</Typography>;
    }
  };

  return <>{renderContent()}</>;
};
