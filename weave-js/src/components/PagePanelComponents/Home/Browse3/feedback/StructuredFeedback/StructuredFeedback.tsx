import React, { SyntheticEvent, useEffect, useState, useCallback, useMemo } from 'react';
import { useWFHooks } from '../../pages/wfReactInterface/context';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { LoadingDots } from '@wandb/weave/components/LoadingDots';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { Checkbox } from '@mui/material';
import { FeedbackCreateReq, FeedbackCreateRes, FeedbackReplaceReq, FeedbackReplaceRes } from '../../pages/wfReactInterface/traceServerClientTypes';
import {TextField} from '@wandb/weave/components/Form/TextField';
import debounce from 'lodash/debounce';
import { Autocomplete, TextField as MuiTextField } from '@mui/material';
import { MOON_300, MOON_500 } from '@wandb/weave/common/css/color.styles';

// Constants
const STRUCTURED_FEEDBACK_TYPE = 'wandb.structuredFeedback.1';
const FEEDBACK_TYPES = {
  NUMERICAL: 'NumericalFeedback',
  TEXT: 'TextFeedback',
  CATEGORICAL: 'CategoricalFeedback',
  BOOLEAN: 'BooleanFeedback',
};
const DEBOUNCE_VAL = 150;

// Interfaces
interface StructuredFeedbackProps {
  sfData: any;
  callRef: string;
  entity: string;
  project: string;
  readOnly?: boolean;
}

// Utility function for creating feedback request
const createFeedbackRequest = (props: StructuredFeedbackProps, value: any, currentFeedbackId: string | null) => {
  const baseRequest = {
    project_id: `${props.entity}/${props.project}`,
    weave_ref: props.callRef,
    creator: null,
    feedback_type: STRUCTURED_FEEDBACK_TYPE,
    payload: {
      value,
      ref: props.sfData.ref,
      name: props.sfData.name,
    },
    sort_by: [{ created_at: 'desc' }],
  };

  if (currentFeedbackId) {
    return { ...baseRequest, feedback_id: currentFeedbackId };
  }

  return baseRequest;
};

export const StructuredFeedbackCell: React.FC<StructuredFeedbackProps> = (props) => {
  const { useFeedback } = useWFHooks();
  const query = useFeedback({
    entity: props.entity,
    project: props.project,
    weaveRef: props.callRef,
  });

  const [currentFeedbackId, setCurrentFeedbackId] = useState<string | null>(null);
  const [foundValue, setFoundValue] = useState<string | number | null>(null);
  const getTsClient = useGetTraceServerClientContext();

  useEffect(() => {
    return getTsClient().registerOnFeedbackListener(props.callRef, query.refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (props.callRef !== query?.result?.[0]?.weave_ref) {
        // The call was changed without the component unmounted, we need to reset
        setFoundValue(null);
        setCurrentFeedbackId(null);
    }
  }, [props.callRef]);

  const onAddFeedback = async (value: any, currentFeedbackId: string | null): Promise<boolean> => {
    const tsClient = getTsClient();

    if (!tsClient) {
      console.error('Failed to get trace server client');
      return false;
    }

    try {
      let res: FeedbackCreateRes | FeedbackReplaceRes;

      if (currentFeedbackId) {
        const replaceRequest = createFeedbackRequest(props, value, currentFeedbackId) as FeedbackReplaceReq;
        res = await tsClient.feedbackReplace(replaceRequest);
      } else {
        const createRequest = createFeedbackRequest(props, value, null) as FeedbackCreateReq;
        res = await tsClient.feedbackCreate(createRequest);
      }

      if (res.reason) {
        console.error(`Feedback ${currentFeedbackId ? 'replace' : 'create'} failed:`, res.reason);
        return false;
      }

      if (res.id) {
        setCurrentFeedbackId(res.id);
        return true;
      }

      return false;
    } catch (error) {
      console.error(`Error in onAddFeedback:`, error);
      return false;
    }
  };

  useEffect(() => {
    if (query?.loading) return;

    // 3 conditions must be true for the feedback to be valid for this component:
    // 1. Feedback is for this feedback spec
    // 2. Feedback is for this structured feedback type
    // 3. Feedback is for this structured feedback name

    const feedbackTypeMatches = (feedback: any) => feedback.feedback_type === STRUCTURED_FEEDBACK_TYPE; 
    const feedbackNameMatches = (feedback: any) => feedback.payload.name === props.sfData.name;
    const feedbackSpecMatches = (feedback: any) => feedback.payload.ref === props.sfData.ref;

    const currFeedback = query.result?.find((feedback: any) => feedbackTypeMatches(feedback) && feedbackNameMatches(feedback) && feedbackSpecMatches(feedback));
    if (!currFeedback) {
        return;
    }

    setCurrentFeedbackId(currFeedback.id);
    setFoundValue(currFeedback?.payload?.value ?? null);
  }, [query?.result, query?.loading, props.sfData]);

  if (query?.loading) return <LoadingDots />;

  if (props.readOnly) {
    return <div className="flex justify-center w-full">
      {foundValue}
    </div>
  }

  return (
    <div className="flex justify-center w-full p-6">
      {renderFeedbackComponent()}
    </div>
  );

  function renderFeedbackComponent() {
    switch (props.sfData.type) {
      case FEEDBACK_TYPES.NUMERICAL:
        return (
          <NumericalFeedbackColumn
            min={props.sfData.min}
            max={props.sfData.max}
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as number | null}
            currentFeedbackId={currentFeedbackId}
          />
        );
      case FEEDBACK_TYPES.TEXT:
        return (
          <TextFeedbackColumn
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as string | null}
            currentFeedbackId={currentFeedbackId}
          />
        );
      case FEEDBACK_TYPES.CATEGORICAL:
        return (
          <CategoricalFeedbackColumn
            options={props.sfData.options}
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as string | null}
            currentFeedbackId={currentFeedbackId}
            multiSelect={props.sfData.multi_select}
            addNewOption={props.sfData.add_new_option}
          />
        );
      case FEEDBACK_TYPES.BOOLEAN:
        return (
          <BinaryFeedbackColumn
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as string | null}
            currentFeedbackId={currentFeedbackId}
          />
        );
      default:
        return <div>Unknown feedback type</div>;
    }
  }
};

export const NumericalFeedbackColumn = ({min, max, onAddFeedback, defaultValue, currentFeedbackId}: {min: number, max: number, onAddFeedback?: (value: number, currentFeedbackId: string | null) => Promise<boolean>, defaultValue: number | null, currentFeedbackId?: string | null}) => {
    const [value, setValue] = useState<number | undefined>(defaultValue ?? undefined);
    const [error, setError] = useState<boolean>(false);

    useEffect(() => {
        setValue(defaultValue ?? undefined);
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: number) => {
            onAddFeedback?.(val, currentFeedbackId ?? null);
        }, DEBOUNCE_VAL),
        [onAddFeedback, currentFeedbackId]
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
    }

    return <div className='w-full'>
        <div className='text-xs text-moon-500 mb-1'>min: {min}, max: {max}</div>
        <TextField
            type="number"
            value={value?.toString() ?? ''}
            onChange={onValueChange}
            placeholder='...'
            errorState={error}
        />
    </div>
}

export const TextFeedbackColumn = ({onAddFeedback, defaultValue, currentFeedbackId}: {onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, defaultValue: string | null, currentFeedbackId?: string | null}) => {
    const [value, setValue] = useState<string>(defaultValue ?? '');

    useEffect(() => {
        setValue(defaultValue ?? '');
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: string) => {
            onAddFeedback?.(val, currentFeedbackId ?? null);
        }, DEBOUNCE_VAL),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (newValue: string) => {
        setValue(newValue);
        debouncedOnAddFeedback(newValue);
    }

    return <div className='w-full'>
        <TextField value={value} onChange={onValueChange} placeholder='...'/>
    </div>
}

type Option = {
  label: string;
  value: string;
}

export const CategoricalFeedbackColumn = ({
    options, 
    onAddFeedback, 
    defaultValue, 
    currentFeedbackId,
    multiSelect,
    addNewOption,
}: {
    options: string[], 
    onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, 
    defaultValue: string | null, 
    currentFeedbackId?: string | null,
    multiSelect: boolean,
    addNewOption: boolean
}) => {
    const dropdownOptions = useMemo(() => {
      const opts = options.map((option: string) => ({
        label: option,
        value: option,
      }));
      opts.splice(0, 0, {label: "", value: ""});
      return opts;
    }, [options, addNewOption]);
    const [value, setValue] = useState<Option>(dropdownOptions[0]);

    useEffect(() => {
      setValue(dropdownOptions.find(option => option.value === defaultValue) ?? dropdownOptions[0]);
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: string) => {
            onAddFeedback?.(val, currentFeedbackId ?? null);
        }, DEBOUNCE_VAL),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (e: any, newValue: Option) => {
        setValue(newValue);
        debouncedOnAddFeedback(newValue?.value ?? '');
    }

    return (
        <Tailwind>
            <div className="flex w-full">
                <Autocomplete
                    options={dropdownOptions}
                    getOptionLabel={(option) => option.label}
                    onChange={onValueChange}
                    value={value}
                    renderInput={(params) => (
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
                        minWidth: '244px',
                        width: 'auto',
                    }}
                    fullWidth
                    ListboxProps={{
                        style: {
                            maxHeight: '200px',
                        },
                    }}
                    renderOption={(props, option) => (
                        <li {...props} style={{ minHeight: '30px' }}>
                            {option.label || <span>&nbsp;</span>}
                        </li>
                    )}
                />
            </div>
        </Tailwind>
    );
}

export const BinaryFeedbackColumn = ({onAddFeedback, defaultValue, currentFeedbackId}: {onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, defaultValue: string | null, currentFeedbackId: string | null}) => {
    const [value, setValue] = useState<boolean | null>(null);

    useEffect(() => {
        setValue(defaultValue === 'true');
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: string) => {
            onAddFeedback?.(val, currentFeedbackId);
        }, DEBOUNCE_VAL),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (e: SyntheticEvent<HTMLInputElement>) => {
        const val = (e.target as HTMLInputElement).checked ? 'true' : 'false';
        setValue(val === 'true');
        debouncedOnAddFeedback(val);
    }

    return <Tailwind>
        <div className="flex justify-center w-full">
            <Checkbox checked={value ?? false} onChange={onValueChange}/>
        </div>
    </Tailwind>
}
