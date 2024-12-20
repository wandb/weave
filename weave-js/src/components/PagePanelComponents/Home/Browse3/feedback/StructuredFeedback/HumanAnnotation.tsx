import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {CellValueString} from '../../../Browse2/CellValueString';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../../pages/wfReactInterface/traceServerClientContext';
import {
  FeedbackCreateError,
  FeedbackCreateSuccess,
} from '../../pages/wfReactInterface/traceServerClientTypes';
import {
  FEEDBACK_TYPE_OPTIONS,
  HumanAnnotation,
  HumanAnnotationPayload,
  makeAnnotationFeedbackType,
  tsHumanAnnotationSpec,
} from './humanAnnotationTypes';

const DEBOUNCE_VAL = 200;

// Interfaces
type HumanAnnotationProps = {
  entity: string;
  project: string;
  viewer: string | null;
  hfSpec: tsHumanAnnotationSpec;
  callRef: string;
  readOnly?: boolean;
  focused?: boolean;
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
};

export const HumanAnnotationCell: React.FC<HumanAnnotationProps> = props => {
  const getTsClient = useGetTraceServerClientContext();
  const tsClient = getTsClient();
  const {useFeedback} = useWFHooks();
  const [foundFeedback, setFoundFeedback] = useState<HumanAnnotation[]>([]);
  const query = useFeedback({
    entity: props.entity,
    project: props.project,
    weaveRef: props.callRef,
  });
  const foundFeedbackCallRef = query?.result?.[0]?.weave_ref;
  const feedbackSpecRef = props.hfSpec.ref;

  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(
      props.callRef,
      query.refetch
    );
  }, [props.callRef, query.refetch, getTsClient]);

  useEffect(() => {
    if (foundFeedbackCallRef && props.callRef !== foundFeedbackCallRef) {
      // The call was changed, we need to reset
      setFoundFeedback([]);
    }
  }, [props.callRef, foundFeedbackCallRef]);

  const onAddFeedback = async (value: number | string): Promise<boolean> => {
    try {
      const requestProps: FeedbackRequestProps = {
        entity: props.entity,
        project: props.project,
        viewer: props.viewer,
        callRef: props.callRef,
        feedbackSpecRef,
        value,
      };
      const createRequest = generateFeedbackRequestPayload(requestProps);
      const promise = tsClient.feedbackCreate(createRequest).then(res => {
        if ('detail' in res) {
          const errorRes = res as FeedbackCreateError;
          toast(`Feedback create failed: ${errorRes.detail}`, {
            type: 'error',
          });
          return false;
        }
        const successRes = res as FeedbackCreateSuccess;
        return !!successRes.id;
      });
      return await promise;
    } catch (error) {
      toast(`Error adding feedback: ${error}`, {
        type: 'error',
      });
      return false;
    }
  };

  useEffect(() => {
    if (query?.loading) {
      return;
    }

    const feedbackRefMatches = (feedback: HumanAnnotation) =>
      feedback.annotation_ref === feedbackSpecRef;

    const currFeedback = query.result?.filter((feedback: HumanAnnotation) =>
      feedbackRefMatches(feedback)
    );
    if (!currFeedback || currFeedback.length === 0) {
      return;
    }

    setFoundFeedback(currFeedback);
  }, [query?.result, query?.loading, feedbackSpecRef]);

  const extractedValues = useMemo(
    () => extractFeedbackValues(foundFeedback, props.viewer, feedbackSpecRef),
    [foundFeedback, props.viewer, feedbackSpecRef]
  );
  const {rawValues, mostRecentVal, viewerFeedbackVal} = extractedValues;

  const type = useMemo(
    () => inferTypeFromJsonSchema(props.hfSpec.field_schema ?? {}),
    [props.hfSpec.field_schema]
  );

  if (query?.loading) {
    return <LoadingDots />;
  }
  if (props.readOnly) {
    return (
      <div className="flex w-full justify-center">
        <CellValueString value={rawValues?.join(', ')} />
      </div>
    );
  }
  let foundValue = mostRecentVal;
  if (props.hfSpec.unique_among_creators) {
    foundValue = viewerFeedbackVal;
  }
  return (
    <div className="w-full py-4">
      <FeedbackComponentSelector
        type={type}
        jsonSchema={props.hfSpec.field_schema ?? {}}
        focused={props.focused ?? false}
        onAddFeedback={onAddFeedback}
        foundValue={foundValue}
        feedbackSpecRef={feedbackSpecRef}
        setUnsavedFeedbackChanges={props.setUnsavedFeedbackChanges}
      />
    </div>
  );
};

const FeedbackComponentSelector: React.FC<{
  type: string | null;
  jsonSchema: Record<string, any>;
  focused: boolean;
  onAddFeedback: (value: any) => Promise<boolean>;
  foundValue: string | number | boolean | null;
  feedbackSpecRef: string;
  setUnsavedFeedbackChanges: React.Dispatch<
    React.SetStateAction<Record<string, () => Promise<boolean>>>
  >;
}> = React.memo(
  ({
    type,
    jsonSchema,
    focused,
    onAddFeedback,
    foundValue,
    feedbackSpecRef,
    setUnsavedFeedbackChanges,
  }) => {
    const wrappedOnAddFeedback = useCallback(
      async (value: any) => {
        if (value == null || value === foundValue || value === '') {
          // Remove from unsaved changes if value is invalid
          setUnsavedFeedbackChanges(curr => {
            const rest = {...curr};
            delete rest[feedbackSpecRef];
            return rest;
          });
          return true;
        }
        setUnsavedFeedbackChanges(curr => ({
          ...curr,
          [feedbackSpecRef]: () => onAddFeedback(value),
        }));
        return true;
      },
      [onAddFeedback, setUnsavedFeedbackChanges, feedbackSpecRef, foundValue]
    );

    switch (type) {
      case 'integer':
        return (
          <NumericalFeedbackColumn
            min={jsonSchema.minimum}
            max={jsonSchema.maximum}
            isInteger={true}
            onAddFeedback={wrappedOnAddFeedback}
            defaultValue={foundValue as number | null}
            focused={focused}
          />
        );
      case 'number':
        return (
          <NumericalFeedbackColumn
            min={jsonSchema.minimum}
            max={jsonSchema.maximum}
            isInteger={false}
            onAddFeedback={wrappedOnAddFeedback}
            defaultValue={foundValue as number | null}
            focused={focused}
          />
        );
      case 'string':
        return (
          <TextFeedbackColumn
            onAddFeedback={wrappedOnAddFeedback}
            defaultValue={foundValue as string | null}
            focused={focused}
            maxLength={jsonSchema.maxLength ?? undefined}
          />
        );
      case 'enum':
        return (
          <EnumFeedbackColumn
            options={jsonSchema.enum}
            onAddFeedback={wrappedOnAddFeedback}
            defaultValue={foundValue as string | null}
            focused={focused}
          />
        );
      case 'boolean':
        return (
          <BinaryFeedbackColumn
            onAddFeedback={wrappedOnAddFeedback}
            defaultValue={foundValue as boolean | null}
            focused={focused}
          />
        );
      default:
        return <></>;
    }
  }
);

type ExtractedFeedbackValues = {
  // The leaves of the feedback tree, just the raw values
  rawValues: Array<string | number>;
  // The most recent feedback value from the CURRENT viewer
  viewerFeedbackVal: string | number | null;
  // The most recent feedback value from ANY viewer
  mostRecentVal: string | number | null;
  // The combined feedback from all viewers
  // userId : value
  combinedFeedback: Record<string, string>;
};

const extractFeedbackValues = (
  foundFeedback: HumanAnnotation[],
  viewer: string | null,
  columnRef: string
): ExtractedFeedbackValues => {
  // filter out feedback for previous columns, then combine by creator
  const combinedFeedback = foundFeedback
    .filter(feedback => feedback.annotation_ref === columnRef)
    .reduce((acc, feedback) => {
      return {
        [feedback.creator ?? '']: feedback.payload.value,
        ...acc,
      };
    }, {}) as Record<string, string>;

  const rawValues = Object.values(combinedFeedback).filter(Boolean);
  const viewerFeedbackVal = combinedFeedback[viewer ?? ''] ?? null;
  const mostRecentVal = foundFeedback[0]?.payload.value ?? null;

  return {
    rawValues,
    viewerFeedbackVal,
    mostRecentVal,
    combinedFeedback,
  };
};

type FeedbackRequestProps = {
  entity: string;
  project: string;
  viewer: string | null;
  callRef: string;
  feedbackSpecRef: string;
  value: any;
};

// Utility function for creating feedback request
const generateFeedbackRequestPayload = ({
  entity,
  project,
  viewer,
  callRef,
  feedbackSpecRef,
  value,
}: FeedbackRequestProps) => {
  const parsedRef = parseRef(feedbackSpecRef);
  const humanAnnotationPayload: HumanAnnotationPayload = {
    value,
  };
  const feedbackType = makeAnnotationFeedbackType(parsedRef.artifactName);
  const baseRequest = {
    project_id: `${entity}/${project}`,
    weave_ref: callRef,
    creator: viewer,
    feedback_type: feedbackType,
    annotation_ref: feedbackSpecRef,
    payload: humanAnnotationPayload,
    sort_by: [{created_at: 'desc'}],
  };
  return baseRequest;
};

const inferTypeFromJsonSchema = (jsonSchema: Record<string, any>) => {
  if ('enum' in jsonSchema) {
    return 'enum';
  }
  if (FEEDBACK_TYPE_OPTIONS.includes(jsonSchema.type)) {
    return jsonSchema.type;
  }
  return null;
};

export const NumericalFeedbackColumn = ({
  min,
  max,
  onAddFeedback,
  defaultValue,
  focused,
  isInteger,
}: {
  min: number;
  max: number;
  onAddFeedback?: (value: number | null) => Promise<boolean>;
  defaultValue: number | null;
  focused?: boolean;
  isInteger?: boolean;
}) => {
  return (
    <NumericalTextField
      value={defaultValue}
      onChange={value => onAddFeedback?.(value)}
      min={min}
      max={max}
      isInteger={isInteger}
      autoFocus={focused}
    />
  );
};

export const TextFeedbackColumn = ({
  onAddFeedback,
  defaultValue,
  focused,
  maxLength,
}: {
  onAddFeedback?: (value: string) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
  maxLength?: number;
}) => {
  const [value, setValue] = useState<string>(defaultValue ?? '');

  const debouncedFn = useMemo(
    () => _.debounce((val: string) => onAddFeedback?.(val), DEBOUNCE_VAL),
    [onAddFeedback]
  );
  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      debouncedFn.cancel();
    };
  }, [debouncedFn]);

  useEffect(() => {
    setValue(defaultValue ?? '');
  }, [defaultValue]);

  const onValueChange = useCallback(
    (newValue: string) => {
      setValue(newValue);
      debouncedFn(newValue);
    },
    [debouncedFn]
  );

  return (
    <div className="w-full">
      <TextField
        autoFocus={focused}
        value={value}
        onChange={onValueChange}
        maxLength={maxLength}
        placeholder=""
      />
      {maxLength && (
        <div className="mb-1 mt-4 text-xs text-moon-500">
          {`Maximum characters: ${maxLength}`}
        </div>
      )}
    </div>
  );
};

type Option = {
  label: string;
  value: string;
};

export const EnumFeedbackColumn = ({
  options,
  onAddFeedback,
  defaultValue,
  focused,
}: {
  options: string[];
  onAddFeedback?: (value: string) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
}) => {
  const dropdownOptions = useMemo(() => {
    const opts = options.map((option: string) => ({
      label: option,
      value: option,
    }));
    return opts;
  }, [options]);
  const [value, setValue] = useState<Option | null>(null);

  useEffect(() => {
    const found = dropdownOptions.find(option => option.value === defaultValue);
    if (found != null) {
      setValue(found);
    }
  }, [defaultValue, dropdownOptions]);

  const onValueChange = useCallback(
    (newValue: Option | null) => {
      setValue(newValue);
      onAddFeedback?.(newValue?.value ?? '');
    },
    [onAddFeedback]
  );

  return (
    <Select
      autoFocus={focused}
      options={dropdownOptions}
      value={value}
      onChange={onValueChange}
    />
  );
};

export const BinaryFeedbackColumn = ({
  onAddFeedback,
  defaultValue,
  focused,
}: {
  onAddFeedback?: (value: any) => Promise<boolean>;
  defaultValue: boolean | null;
  focused?: boolean;
}) => {
  const [value, setValue] = useState<boolean | null>(defaultValue);

  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleClick = (newValue: boolean) => {
    // If clicking the same value, deselect it
    const valueToSet = value === newValue ? null : newValue;
    setValue(valueToSet);
    onAddFeedback?.(valueToSet);
  };

  return (
    <Tailwind>
      <div className="flex w-full justify-center gap-10">
        <Button
          variant={value === true ? 'primary' : 'secondary'}
          onClick={() => handleClick(true)}
          autoFocus={focused}>
          True
        </Button>
        <Button
          variant={value === false ? 'primary' : 'secondary'}
          onClick={() => handleClick(false)}>
          False
        </Button>
        <div className="flex-grow" />
      </div>
    </Tailwind>
  );
};

export interface NumericalTextFieldProps {
  value: number | null;
  onChange: (value: number | null) => void;
  min?: number;
  max?: number;
  isInteger?: boolean;
  autoFocus?: boolean;
  placeholder?: string;
}

export const NumericalTextField: React.FC<NumericalTextFieldProps> = ({
  value,
  onChange,
  min,
  max,
  isInteger,
  autoFocus,
  placeholder,
}) => {
  const [textValue, setTextValue] = useState<string>(value?.toString() ?? '');
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    setTextValue(value?.toString() ?? '');
  }, [value]);

  const getVal = useCallback(
    (v: string) => {
      if (v === '') {
        return null;
      }
      if (isInteger) {
        const intRegExp = new RegExp('^[+-]?[0-9]+$');
        return intRegExp.test(v) ? v : null;
      }
      const floatRegExp = new RegExp('^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$');
      return floatRegExp.test(v) ? v : null;
    },
    [isInteger]
  );

  const onValueChange = useCallback(
    (v: string) => {
      // Allow empty string
      if (v === '') {
        setTextValue('');
        setError(false);
        onChange(null);
        return;
      }

      const val = getVal(v);
      if (val === textValue) {
        return;
      }
      setTextValue(v);

      // If val is null but v isn't empty, there's a format error
      if (val === null) {
        setError(true);
        onChange(null);
        return;
      }

      const parsedVal = isInteger ? parseInt(val, 10) : parseFloat(val);
      if (
        (min != null && parsedVal < min) ||
        (max != null && parsedVal > max)
      ) {
        setError(true);
        onChange(null);
        return;
      }

      setError(false);
      onChange(parsedVal);
    },
    [textValue, min, max, isInteger, onChange, getVal]
  );

  return (
    <div className="w-full">
      <TextField
        autoFocus={autoFocus}
        type={isInteger ? 'number' : 'text'}
        value={textValue}
        onChange={onValueChange}
        placeholder={placeholder}
        step={isInteger ? 1 : 0.001}
        errorState={error}
      />
      {(min != null || max != null) && (
        <div className="mb-1 mt-4 text-xs text-moon-500">
          {isInteger ? 'Integer required. ' : ''}
          {min != null && `Min: ${min}`}
          {min != null && max != null && ', '}
          {max != null && `Max: ${max}`}
        </div>
      )}
    </div>
  );
};
