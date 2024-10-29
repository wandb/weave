import {Checkbox} from '@mui/material';
import {Autocomplete, TextField as MuiTextField} from '@mui/material';
import { toast } from '@wandb/weave/common/components/elements/Toast';
import {MOON_300} from '@wandb/weave/common/css/color.styles';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import debounce from 'lodash/debounce';
import React, {
  SyntheticEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { CellValueString } from '../../../Browse2/CellValueString';
import {useWFHooks} from '../../pages/wfReactInterface/context';
import {useGetTraceServerClientContext} from '../../pages/wfReactInterface/traceServerClientContext';
import {
  FeedbackCreateError,
  FeedbackCreateSuccess,
} from '../../pages/wfReactInterface/traceServerClientTypes';
import { HumanAnnotationPayload, HumanFeedback, tsHumanFeedbackColumn} from './humanFeedbackTypes';
import { parseRef } from '@wandb/weave/react';

// Constants
const HUMAN_FEEDBACK_TYPE = 'wandb.human_annotation.1';
const MAGIC_FEEDBACK_TYPES = {
  NUMERICAL: 'number',
  TEXT: 'text',
  BOOLEAN: 'boolean',
  CATEGORICAL: 'categorical',
}
const DEBOUNCE_VAL = 200;

// Interfaces
interface HumanFeedbackProps {
  entity: string;
  project: string;
  viewer: string | null;
  hfColumn: tsHumanFeedbackColumn;
  callRef: string;
  readOnly?: boolean;
  focused?: boolean;
}

// Utility function for creating feedback request
const createFeedbackRequest = (
  props: HumanFeedbackProps,
  value: any,
) => {
  const ref = props.hfColumn.ref;
  const parsedRef = parseRef(ref);
  const humanAnnotationPayload: HumanAnnotationPayload = {
    annotation_column_ref: ref,
    value: {
      [parsedRef.artifactName]: {
        [parsedRef?.artifactVersion]: value
      }
    }
  };

  const baseRequest = {
    project_id: `${props.entity}/${props.project}`,
    weave_ref: props.callRef,
    creator: props.viewer,
    feedback_type: HUMAN_FEEDBACK_TYPE,
    payload: humanAnnotationPayload,
    sort_by: [{created_at: 'desc'}],
  };

  return baseRequest;
};

const renderFeedbackComponent = (
  props: HumanFeedbackProps,
  onAddFeedback: (value: any) => Promise<boolean>,
  foundValue: string | number | null,
) => {
  // TODO validation on json_schema
  switch (props.hfColumn.json_schema.type) {
    case MAGIC_FEEDBACK_TYPES.NUMERICAL:
      const numericalFeedback = props.hfColumn.json_schema;
      return (
        <NumericalFeedbackColumn
          min={numericalFeedback.min}
          max={numericalFeedback.max}
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as number | null}
          focused={props.focused}
        />
      );
    case MAGIC_FEEDBACK_TYPES.TEXT:
      return (
        <TextFeedbackColumn
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={props.focused}
        />
      );
    case MAGIC_FEEDBACK_TYPES.CATEGORICAL:
      const categoricalFeedback = props.hfColumn.json_schema;
      return (
        <CategoricalFeedbackColumn
          options={categoricalFeedback.options}
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={props.focused}
        />
      );
    case MAGIC_FEEDBACK_TYPES.BOOLEAN:
      return (
        <BinaryFeedbackColumn
          onAddFeedback={onAddFeedback}
          defaultValue={foundValue as string | null}
          focused={props.focused}
        />
      );
    default:
      return <div>Unknown feedback type</div>;
  }
};

export const HumanFeedbackCell: React.FC<
  HumanFeedbackProps
> = props => {
  const {useFeedback} = useWFHooks();
  const query = useFeedback({
    entity: props.entity,
    project: props.project,
    weaveRef: props.callRef,
  });
  const [foundFeedback, setFoundFeedback] = useState<HumanFeedback[]>([]);
  const getTsClient = useGetTraceServerClientContext();

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
    if (props.callRef !== query?.result?.[0]?.weave_ref) {
      // The call was changed, we need to reset
      setFoundFeedback([]);
    }
  }, [props.callRef, query?.result]);

  const onAddFeedback = async (value: number | string): Promise<boolean> => {
    const tsClient = getTsClient();

    if (!tsClient) {
      console.error('Failed to get trace server client');
      return false;
    }

    try {
      const createRequest = createFeedbackRequest(props, value);
      const res = await tsClient.feedbackCreate(createRequest);
      if ('detail' in res) {
        const errorRes = res as FeedbackCreateError;
        toast(`Feedback create failed: ${errorRes.detail}`, {
          type: 'error',
        });
        return false;
      }
      const successRes = res as FeedbackCreateSuccess;
      if (successRes.id) {
        return true;
      }
      return false;
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
      feedback.payload.annotation_column_ref === props.hfColumn.ref;

    const currFeedback = query.result?.filter(
      (feedback: HumanFeedback) =>
        feedbackRefMatches(feedback)
    );
    if (!currFeedback || currFeedback.length === 0) {
      return;
    }

    setFoundFeedback(currFeedback);
  }, [query?.result, query?.loading, props.hfColumn]);

  // userId -> objectId -> objectHash : value
  const combinedFeedback = foundFeedback.reduce((acc, feedback) => {
    return {
      [feedback.creator ?? '']: feedback.payload.value,
      ...acc,
    };
  }, {}) as Record<string, Record<string, Record<string, string>>>;
  
  const parsedRef = parseRef(props.hfColumn.ref);
  const rawValues = useMemo(() => {
    let values = [];
    for (const payload of Object.values(combinedFeedback)) {
      const pRecord = payload as Record<string, Record<string, string>>;
      values.push(pRecord[parsedRef.artifactName]?.[parsedRef.artifactVersion]);
    }
    return values;
  }, [combinedFeedback, parsedRef]);

  const viewerFeedbackVal = props.viewer ? combinedFeedback[props.viewer]?.[parsedRef.artifactName]?.[parsedRef.artifactVersion] : null;
  if (query?.loading) {
    return <LoadingDots />;
  }

  if (props.readOnly) {
    // TODO: make this prettier, for now just join with commas
    return <div className="flex w-full justify-center">
      <CellValueString value={rawValues?.join(', ')} />
    </div>;
  }

  return (
    <div className="w-full py-4">
      {renderFeedbackComponent(props, onAddFeedback, viewerFeedbackVal)}
    </div>
  );
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
  onAddFeedback?: (value: number) => Promise<boolean>;
  defaultValue: number | null;
  focused?: boolean;
  isInteger?: boolean;
}) => {
  const [value, setValue] = useState<number | undefined>(
    defaultValue ?? undefined
  );
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    setValue(defaultValue ?? undefined);
  }, [defaultValue]);

  const debouncedOnAddFeedback = useCallback(
    debounce((val: number) => {
      onAddFeedback?.(val);
    }, DEBOUNCE_VAL),
    [onAddFeedback]
  );

  const onValueChange = (v: string) => {
    const val = parseInt(v);
    setValue(val);
    if (val < min || val > max) {
      setError(true);
      return;
    } else {
      setError(false);
    }
    debouncedOnAddFeedback(val);
  };

  return (
    <div className="w-full">
      <div className="mb-1 text-xs text-moon-500">
        min: {min}, max: {max}
      </div>
      <TextField
        autoFocus={focused}
        type="number"
        value={value?.toString() ?? ''}
        onChange={onValueChange}
        placeholder="..."
        step={isInteger ? 1 : 0.001}
        errorState={error}
      />
    </div>
  );
};

export const TextFeedbackColumn = ({
  onAddFeedback,
  defaultValue,
  focused,
}: {
  onAddFeedback?: (
    value: string,
  ) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
}) => {
  const [value, setValue] = useState<string>(defaultValue ?? '');

  useEffect(() => {
    setValue(defaultValue ?? '');
  }, [defaultValue]);

  const debouncedOnAddFeedback = useCallback(
    debounce((val: string) => {
      onAddFeedback?.(val);
    }, DEBOUNCE_VAL),
    [onAddFeedback]
  );

  const onValueChange = (newValue: string) => {
    setValue(newValue);
    debouncedOnAddFeedback(newValue);
  };

  return (
    <div className="w-full pb-4">
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
  onAddFeedback?: (
    value: string,
  ) => Promise<boolean>;
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

  const debouncedOnAddFeedback = useCallback(
    debounce((val: string) => {
      onAddFeedback?.(val);
    }, DEBOUNCE_VAL),
    [onAddFeedback]
  );

  const onValueChange = (e: any, newValue: Option) => {
    setValue(newValue);
    debouncedOnAddFeedback(newValue?.value ?? '');
  };

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
  onAddFeedback?: (
    value: string,
  ) => Promise<boolean>;
  defaultValue: string | null;
  focused?: boolean;
}) => {
  const [value, setValue] = useState<boolean | null>(null);

  useEffect(() => {
    setValue(defaultValue === 'true');
  }, [defaultValue]);

  const debouncedOnAddFeedback = useCallback(
    debounce((val: string) => {
      onAddFeedback?.(val);
    }, DEBOUNCE_VAL),
    [onAddFeedback]
  );

  const onValueChange = (e: SyntheticEvent<HTMLInputElement>) => {
    const val = (e.target as HTMLInputElement).checked ? 'true' : 'false';
    setValue(val === 'true');
    debouncedOnAddFeedback(val);
  };

  return (
    <Tailwind>
      <div className="flex w-full justify-center">
        <Checkbox
          autoFocus={focused}
          checked={value ?? false}
          onChange={onValueChange}
        />
      </div>
    </Tailwind>
  );
};
