import {
  Box,
  Checkbox,
  FormControl,
  FormControlLabel,
  InputLabel,
} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {z} from 'zod';

import {
  AutocompleteWithLabel,
  GAP_BETWEEN_ITEMS_PX,
  GAP_BETWEEN_LABEL_AND_FIELD_PX,
  TextFieldWithLabel,
} from './FormComponents';

interface ZSFormProps {
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

const distiminatorOptionToValue = (
  option: z.ZodTypeAny,
  discriminator: string
) => {
  return option._def.shape()[discriminator]._def.value;
};

const Label: React.FC<{label: string}> = ({label}) => {
  return (
    <InputLabel style={{marginBottom: GAP_BETWEEN_LABEL_AND_FIELD_PX + 'px'}}>
      {label}
    </InputLabel>
  );
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
    value?.[discriminator] ||
    distiminatorOptionToValue(options[0], discriminator);

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
    <Box style={{marginBottom: GAP_BETWEEN_ITEMS_PX + 'px'}}>
      <AutocompleteWithLabel
        label={keyName}
        options={options.map(option => ({
          value: distiminatorOptionToValue(option, discriminator),
          label: distiminatorOptionToValue(option, discriminator),
        }))}
        value={{
          value: currentType,
          label: currentType,
        }}
        onChange={v => {
          handleTypeChange(v.value as string);
        }}
      />
      <Box mt={2}>
        <ZSForm
          configSchema={filteredSchema}
          config={value || {}}
          setConfig={newConfig => {
            const updatedConfig = {...newConfig, [discriminator]: currentType};
            updateConfig(targetPath, updatedConfig, config, setConfig);
          }}
          path={[]}
        />
      </Box>
    </Box>
  );
};

const NestedForm: React.FC<{
  keyName: string;
  fieldSchema: z.ZodTypeAny;
  config: Record<string, any>;
  setConfig: (config: Record<string, any>) => void;
  path: string[];
  hideLabel?: boolean;
  autoFocus?: boolean;
}> = ({
  keyName,
  fieldSchema,
  config,
  setConfig,
  path,
  hideLabel,
  autoFocus,
}) => {
  const currentPath = useMemo(() => [...path, keyName], [path, keyName]);
  const [currentValue, setCurrentValue] = useState(
    getNestedValue(config, currentPath)
  );

  // Only update parent config on blur, for string fields
  const handleBlur = useCallback(() => {
    if (currentValue !== getNestedValue(config, currentPath)) {
      updateConfig(currentPath, currentValue, config, setConfig);
    }
  }, [currentValue, currentPath, config, setConfig]);
  const handleChange = useCallback((value: string) => {
    setCurrentValue(value);
  }, []);

  // set current value for non-string fields
  useEffect(() => {
    setCurrentValue(getNestedValue(config, currentPath));
  }, [config, currentPath]);

  const unwrappedSchema = unwrapSchema(fieldSchema);
  const isOptional = fieldSchema instanceof z.ZodOptional;

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
      <FormControl
        fullWidth
        style={{marginBottom: GAP_BETWEEN_ITEMS_PX + 'px'}}>
        {!hideLabel && <Label label={keyName} />}
        <Box ml={2}>
          <ZSForm
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
    <TextFieldWithLabel
      isOptional={isOptional}
      label={!hideLabel ? keyName : undefined}
      type={fieldType}
      value={currentValue ?? ''}
      onChange={handleChange}
      onBlur={handleBlur}
      autoFocus={autoFocus}
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
  const elementSchema = unwrappedSchema.element;
  const fieldDescription = getFieldDescription(fieldSchema);

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
    <FormControl fullWidth style={{marginBottom: GAP_BETWEEN_ITEMS_PX + 'px'}}>
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <Label label={keyName} />
        {fieldDescription && (
          <DescriptionTooltip description={fieldDescription} />
        )}
      </Box>
      <Box border="1px solid #e0e0e0" borderRadius="4px" p={2}>
        {arrayValue.map((item, index) => (
          <Box
            key={index}
            display="flex"
            flexDirection="column"
            alignItems="flex-start"
            style={{
              width: '100%',
              gap: 4,
              alignItems: 'center',
              height: '35px',
              marginBottom: '16px',
              marginTop: '8px',
              marginLeft: '8px',
            }}>
            <Box flexGrow={1} width="100%" display="flex" alignItems="center">
              <Box flexGrow={1}>
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
                  hideLabel
                  autoFocus={index === arrayValue.length - 1}
                />
              </Box>
              <Box mb={4} ml={4} mr={4}>
                <Button
                  size="small"
                  variant="ghost"
                  icon="delete"
                  tooltip="Remove this entry"
                  disabled={arrayValue.length <= minItems}
                  onClick={() =>
                    removeArrayItem(targetPath, index, config, setConfig)
                  }
                />
              </Box>
            </Box>
          </Box>
        ))}
        <Box mt={2} style={{width: '100%'}}>
          <Button
            variant="secondary"
            icon="add-new"
            className="w-full"
            style={{
              padding: '4px',
              width: '100%',
              marginLeft: '8px',
              marginRight: '8px',
              marginBottom: '8px',
            }}
            onClick={() =>
              addArrayItem(targetPath, elementSchema, config, setConfig)
            }>
            Add item
          </Button>
        </Box>
      </Box>
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
  noMarginBottom?: boolean;
  noLabel?: boolean;
}> = ({
  keyName,
  fieldSchema,
  unwrappedSchema,
  targetPath,
  value,
  config,
  setConfig,
  noMarginBottom,
  noLabel,
}) => {
  const options: string[] = unwrappedSchema.options;

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
    <AutocompleteWithLabel
      label={noLabel ? undefined : keyName}
      options={options.map(option => ({value: option, label: option}))}
      value={{
        value: selectedValue,
        label: selectedValue,
      }}
      onChange={v => updateConfig(targetPath, v.value, config, setConfig)}
      style={{
        marginBottom: noMarginBottom ? '0px' : GAP_BETWEEN_ITEMS_PX + 'px',
      }}
    />
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
    <FormControl fullWidth style={{marginBottom: GAP_BETWEEN_ITEMS_PX + 'px'}}>
      <Label label={keyName} />
      {internalPairs.map(({key, value: innerValue}, index) => (
        <Box
          key={index}
          display="flex"
          alignItems="center"
          style={{
            width: '100%',
            gap: 4,
            alignItems: 'center',
            height: '35px',
            marginBottom: '4px',
          }}>
          <Box style={{flex: '1 1 50%'}}>
            <TextFieldWithLabel
              style={{
                marginBottom: '0px',
              }}
              value={key}
              onChange={newValue => {
                if (
                  internalPairs.some(
                    (pair, i) => i !== index && pair.key === newValue
                  )
                ) {
                  // Prevent duplicate keys
                  return;
                }
                updateInternalPair(index, newValue, innerValue);
              }}
            />
          </Box>
          <Box style={{flex: '1 1 50%'}}>
            {isZodType(valueSchema, s => s instanceof z.ZodEnum) ? (
              <EnumField
                noMarginBottom
                noLabel
                keyName={key}
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
              <TextFieldWithLabel
                value={innerValue}
                onChange={newValue => updateInternalPair(index, key, newValue)}
                style={{
                  marginBottom: '0px',
                }}
              />
            )}
          </Box>
          <Button
            size="small"
            variant="ghost"
            icon="delete"
            tooltip="Remove this key"
            onClick={() => removePair(index)}
          />
        </Box>
      ))}
      <Button
        // style={{marginTop: '8px'}}
        size="small"
        variant="secondary"
        onClick={addNewPair}>
        Add Key
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
  const fieldDescription = getFieldDescription(fieldSchema);
  const isOptional = fieldSchema instanceof z.ZodOptional;

  return (
    <Box display="flex" alignContent="center" justifyContent="space-between">
      <TextFieldWithLabel
        label={keyName}
        type="number"
        value={(value ?? '').toString()}
        style={{width: '100%'}}
        isOptional={isOptional}
        onChange={newValue => {
          const finalValue = newValue === '' ? undefined : Number(newValue);
          if (
            finalValue !== undefined &&
            (finalValue < min || finalValue > max)
          ) {
            return;
          }
          updateConfig(targetPath, finalValue, config, setConfig);
        }}
      />
      {fieldDescription && (
        <Box
          display="flex"
          alignItems="center"
          sx={{marginTop: '14px', marginLeft: '2px'}}>
          <DescriptionTooltip description={fieldDescription} />
        </Box>
      )}
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
  const isOptional = fieldSchema instanceof z.ZodOptional;

  useEffect(() => {
    if (value !== literalValue) {
      updateConfig(targetPath, literalValue, config, setConfig);
    }
  }, [value, literalValue, targetPath, config, setConfig]);

  return (
    <TextFieldWithLabel
      isOptional={isOptional}
      label={keyName}
      disabled
      value={literalValue}
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

const DescriptionTooltip: React.FC<{description?: string}> = ({
  description,
}) => {
  if (!description) {
    return null;
  }
  return (
    <Button
      size="small"
      variant="ghost"
      icon="help-alt"
      tooltip={description}
    />
  );
};

/**
 * This component renders a form based on a zod schema.
 * Warning: not all sub types are supported. Add them as needed.
 * Warning2: not all components use the official wandb components yet,
 * you might need to update them.
 */
export const ZSForm: React.FC<ZSFormProps> = ({
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
      return <div>Unsupported schema type</div>;
    }
  };

  return <>{renderContent()}</>;
};
