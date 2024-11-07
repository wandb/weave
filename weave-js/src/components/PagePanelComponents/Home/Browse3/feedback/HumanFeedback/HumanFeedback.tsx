import {Autocomplete, TextField as MuiTextField} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_300} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
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
  HumanAnnotationPayload,
  HumanFeedback,
  tsHumanFeedbackColumn,
} from './humanFeedbackTypes';

// Constants
const HUMAN_FEEDBACK_TYPE = 'wandb.human_annotation.1';
const FEEDBACK_TYPE_OPTIONS = ['text', 'number', 'boolean', 'categorical'];
const DEBOUNCE_VAL = 200;

// Interfaces
type HumanFeedbackProps = {
  entity: string;
  project: string;
  viewer: string | null;
  hfColumn: tsHumanFeedbackColumn;
  callRef: string;
  readOnly?: boolean;
  focused?: boolean;
};

// pending feedback promises, used to wait for all pending feedback to complete
// when clicking the next button in the sidebar outside of this component
const pendingFeedbackPromises = new Set<Promise<boolean>>();

export const HumanFeedbackCell: React.FC<HumanFeedbackProps> = props => {
  const getTsClient = useGetTraceServerClientContext();
  const tsClient = getTsClient();
  const {useFeedback} = useWFHooks();
  const [foundFeedback, setFoundFeedback] = useState<HumanFeedback[]>([]);
  const query = useFeedback({
    entity: props.entity,
    project: props.project,
    weaveRef: props.callRef,
  });
  const foundFeedbackCallRef = query?.result?.[0]?.weave_ref;
  const feedbackColumnRef = props.hfColumn.ref;

  useEffect(() => {
    if (!props.readOnly) {
      // We don't need to listen for feedback changes if the cell is editable
      // it is being controlled by local state
      return;
    }
    return getTsClient().registerOnFeedbackListener(
      props.callRef,
      query.refetch
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        feedbackColumnRef,
        value,
      };

      // TODO(gst): use replace when feedback is updated within 10 seconds of the previous feedback
      const createRequest = createFeedbackRequest(requestProps);
      const promise = tsClient
        .feedbackCreate(createRequest)
        .then(res => {
          if ('detail' in res) {
            const errorRes = res as FeedbackCreateError;
            toast(`Feedback create failed: ${errorRes.detail}`, {
              type: 'error',
            });
            return false;
          }
          const successRes = res as FeedbackCreateSuccess;
          return !!successRes.id;
        })
        .catch(error => {
          toast(`Error in onAddFeedback: ${error}`, {
            type: 'error',
          });
          return false;
        })
        .finally(() => {
          pendingFeedbackPromises.delete(promise);
        });

      pendingFeedbackPromises.add(promise);
      return await promise;
    } catch (error) {
      toast(`Error in onAddFeedback: ${error}`, {
        type: 'error',
      });
      return false;
    }
  };

  useEffect(() => {
    if (query?.loading) {
      return;
    }

    const feedbackRefMatches = (feedback: HumanFeedback) =>
      feedback.payload.annotation_column_ref === feedbackColumnRef;

    const currFeedback = query.result?.filter((feedback: HumanFeedback) =>
      feedbackRefMatches(feedback)
    );
    if (!currFeedback || currFeedback.length === 0) {
      return;
    }

    setFoundFeedback(currFeedback);
  }, [query?.result, query?.loading, feedbackColumnRef]);

  const extractedValues = useMemo(
    () => extractFeedbackValues(foundFeedback, props.viewer, feedbackColumnRef),
    [foundFeedback, props.viewer, feedbackColumnRef]
  );
  const {rawValues, mostRecentVal} = extractedValues;

  const type = useMemo(
    () => inferTypeFromJsonSchema(props.hfColumn.json_schema),
    [props.hfColumn.json_schema]
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

  return (
    <div className="w-full py-4">
      <FeedbackComponentSelector
        type={type}
        jsonSchema={props.hfColumn.json_schema}
        focused={props.focused ?? false}
        onAddFeedback={onAddFeedback}
        foundValue={mostRecentVal}
      />
    </div>
  );
};

const FeedbackComponentSelector: React.FC<{
  type: string | null;
  jsonSchema: Record<string, any>;
  focused: boolean;
  onAddFeedback: (value: any) => Promise<boolean>;
  foundValue: string | number | null;
}> = React.memo(({type, jsonSchema, focused, onAddFeedback, foundValue}) => {
  switch (type) {
    case 'number':
      return (
        <NumericalFeedbackColumn
          min={jsonSchema.min}
          max={jsonSchema.max}
          isInteger={jsonSchema.is_integer}
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as number | null}
          focused={focused}
        />
      );
    case 'text':
      return (
        <TextFeedbackColumn
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={focused}
        />
      );
    case 'categorical':
      return (
        <CategoricalFeedbackColumn
          options={jsonSchema.options}
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={focused}
        />
      );
    case 'boolean':
      return (
        <BinaryFeedbackColumn
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={focused}
        />
      );
    default:
      // Return a text column by default
      return (
        <TextFeedbackColumn
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={focused}
        />
      );
  }
});

type ExtractedFeedbackValues = {
  // The leaves of the feedback tree, just the raw values
  rawValues: Array<string | number>;
  // The most recent feedback value from the CURRENT viewer
  viewerFeedbackVal: string | number | null;
  // The most recent feedback value from ANY viewer
  mostRecentVal: string | number | null;
  // The combined feedback from all viewers
  // userId -> objectId -> objectHash : value
  combinedFeedback: Record<string, Record<string, Record<string, string>>>;
};

const extractFeedbackValues = (
  foundFeedback: HumanFeedback[],
  viewer: string | null,
  columnRef: string
): ExtractedFeedbackValues => {
  const combinedFeedback = foundFeedback.reduce((acc, feedback) => {
    return {
      [feedback.creator ?? '']: feedback.payload.value,
      ...acc,
    };
  }, {}) as Record<string, Record<string, Record<string, string>>>;

  const parsedRef = parseRef(columnRef);
  const rawValues = Object.values(combinedFeedback)
    .map(payload => {
      const pRecord = payload as Record<
        string,
        Record<string, string | number>
      >;
      return pRecord[parsedRef.artifactName]?.[parsedRef.artifactVersion];
    })
    .filter(Boolean);

  const viewerFeedbackVal =
    combinedFeedback[viewer ?? '']?.[parsedRef.artifactName]?.[
      parsedRef.artifactVersion
    ];

  // Get most recent value from the first feedback (since they're sorted by created_at desc)
  const mostRecentVal =
    foundFeedback[0]?.payload.value?.[parsedRef.artifactName]?.[
      parsedRef.artifactVersion
    ] ?? null;

  return {
    rawValues,
    // Currently unused, but likely useful in the future
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
  feedbackColumnRef: string;
  value: any;
};

// Utility function for creating feedback request
const createFeedbackRequest = ({
  entity,
  project,
  viewer,
  callRef,
  feedbackColumnRef,
  value,
}: FeedbackRequestProps) => {
  const parsedRef = parseRef(feedbackColumnRef);
  const humanAnnotationPayload: HumanAnnotationPayload = {
    annotation_column_ref: feedbackColumnRef,
    value: {
      [parsedRef.artifactName]: {
        [parsedRef?.artifactVersion]: value,
      },
    },
  };

  const baseRequest = {
    project_id: `${entity}/${project}`,
    weave_ref: callRef,
    creator: viewer,
    feedback_type: HUMAN_FEEDBACK_TYPE,
    payload: humanAnnotationPayload,
    sort_by: [{created_at: 'desc'}],
  };

  return baseRequest;
};

const inferTypeFromJsonSchema = (jsonSchema: Record<string, any>) => {
  if (jsonSchema.type in FEEDBACK_TYPE_OPTIONS) {
    return jsonSchema.type;
  }
  if (jsonSchema.min !== undefined || jsonSchema.max !== undefined) {
    return 'number';
  }
  if (jsonSchema.max_length !== undefined) {
    return 'text';
  }
  if (jsonSchema.options !== undefined) {
    return 'categorical';
  }
  toast(`Unknown feedback type from spec: ${JSON.stringify(jsonSchema)}`, {
    type: 'warning',
  });
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
  const [value, setValue] = useState<string>(defaultValue?.toString() ?? '');
  const [error, setError] = useState<boolean>(false);

  const debouncedFn = useMemo(
    () =>
      _.debounce((val: number | null) => onAddFeedback?.(val), DEBOUNCE_VAL),
    [onAddFeedback]
  );
  useEffect(() => {
    return () => {
      debouncedFn.cancel();
    };
  }, [debouncedFn]);

  useEffect(() => {
    setValue(defaultValue?.toString() ?? '');
  }, [defaultValue]);

  const getVal = useCallback(
    (v: string) => {
      if (v === '') {
        return null;
      }
      if (isInteger) {
        return v;
      }
      const floatRegExp = new RegExp('^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$');
      if (!floatRegExp.test(v)) {
        return null;
      }
      return v;
    },
    [isInteger]
  );

  const onValueChange = useCallback(
    (v: string) => {
      const val = getVal(v);
      if (val === value) {
        return;
      }
      setValue(v);
      const parsedVal = val
        ? isInteger
          ? parseInt(val, 10)
          : parseFloat(val)
        : null;
      if (parsedVal && (parsedVal < min || parsedVal > max)) {
        setError(true);
        return;
      } else {
        setError(false);
      }
      debouncedFn(parsedVal);
    },
    [value, min, max, isInteger, debouncedFn, getVal]
  );

  return (
    <div className="w-full">
      <TextField
        autoFocus={focused}
        type={isInteger ? 'number' : 'text'}
        value={value?.toString() ?? ''}
        onChange={onValueChange}
        placeholder=""
        step={isInteger ? 1 : 0.001}
        errorState={error}
      />
      <div className="mb-1 text-xs text-moon-500">
        min: {min}, max: {max}
      </div>
    </div>
  );
};

export const TextFeedbackColumn = ({
  onAddFeedback,
  defaultValue,
  focused,
}: {
  onAddFeedback?: (value: string) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
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
        placeholder="..."
      />
    </div>
  );
};

type Option = {
  label: string;
  value: string;
};

export const CategoricalFeedbackColumn = ({
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
    opts.splice(0, 0, {label: '', value: ''});
    return opts;
  }, [options]);

  const [value, setValue] = useState<Option>(dropdownOptions[0]);

  useEffect(() => {
    setValue(
      dropdownOptions.find(option => option.value === defaultValue) ??
        dropdownOptions[0]
    );
  }, [defaultValue, dropdownOptions]);

  const onValueChange = useCallback(
    (e: any, newValue: Option) => {
      if (newValue?.value === value?.value) {
        return;
      }
      setValue(newValue);
      onAddFeedback?.(newValue?.value ?? '');
    },
    [value?.value, onAddFeedback]
  );

  return (
    <div className="flex w-full">
      <Autocomplete
        options={dropdownOptions}
        getOptionLabel={option => option.label}
        onChange={onValueChange}
        value={value}
        openOnFocus
        autoFocus={focused}
        renderInput={params => (
          <MuiTextField
            {...params}
            sx={{
              '& .MuiInputBase-root': {
                height: '38px',
                minHeight: '38px',
                borderColor: MOON_300,
              },
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: MOON_300,
              },
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: MOON_300,
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderColor: MOON_300,
              },
            }}
          />
        )}
        disableClearable
        sx={{
          minWidth: '200px',
          width: '100%',
        }}
        fullWidth
        ListboxProps={{
          style: {
            maxHeight: '200px',
          },
        }}
        renderOption={(props, option) => (
          <li {...props} style={{minHeight: '30px'}}>
            {option.label || <span>&nbsp;</span>}
          </li>
        )}
      />
    </div>
  );
};

export const BinaryFeedbackColumn = ({
  onAddFeedback,
  defaultValue,
  focused,
}: {
  onAddFeedback?: (value: string) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
}) => {
  const [value, setValue] = useState<string | null>(defaultValue);

  useEffect(() => {
    setValue(defaultValue);
  }, [defaultValue]);

  const handleClick = (newValue: string) => {
    // If clicking the same value, deselect it
    const valueToSet = value === newValue ? null : newValue;
    setValue(valueToSet);
    onAddFeedback?.(valueToSet ?? '');
  };

  return (
    <Tailwind>
      <div className="flex w-full justify-center gap-10">
        <Button
          variant={value === 'true' ? 'primary' : 'outline'}
          onClick={() => handleClick('true')}
          autoFocus={focused}>
          True
        </Button>
        <Button
          variant={value === 'false' ? 'primary' : 'outline'}
          onClick={() => handleClick('false')}>
          False
        </Button>
      </div>
    </Tailwind>
  );
};

export const waitForPendingFeedback = async (): Promise<void> => {
  if (pendingFeedbackPromises.size === 0) {
    return;
  }
  await Promise.all(Array.from(pendingFeedbackPromises));
};
