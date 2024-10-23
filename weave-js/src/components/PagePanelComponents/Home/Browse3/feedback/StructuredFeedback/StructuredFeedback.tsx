import React, { SyntheticEvent, useEffect, useState, useCallback } from 'react';
import { useWFHooks } from '../../pages/wfReactInterface/context';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { LoadingDots } from '@wandb/weave/components/LoadingDots';
import Select from 'react-select'
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { Checkbox } from '@mui/material';
import CreatableSelect from 'react-select/creatable';
import { FeedbackCreateReq, FeedbackCreateRes, FeedbackReplaceReq, FeedbackReplaceRes } from '../../pages/wfReactInterface/traceServerClientTypes';
import {TextField} from '@wandb/weave/components/Form/TextField';
import debounce from 'lodash/debounce';

// Constants
const STRUCTURED_FEEDBACK_TYPE = 'wandb.structuredFeedback.1';
const FEEDBACK_TYPES = {
  RANGE: 'RangeFeedback',
  CATEGORICAL: 'CategoricalFeedback',
  BOOLEAN: 'BooleanFeedback',
};

// Interfaces
interface StructuredFeedbackProps {
  structuredFeedbackOptions: any;
  weaveRef: string;
  entity: string;
  project: string;
  feedbackSpecRef: string;
}

// Utility function for creating feedback request
const createFeedbackRequest = (props: StructuredFeedbackProps, value: any, currentFeedbackId: string | null) => {
  const baseRequest = {
    project_id: `${props.entity}/${props.project}`,
    weave_ref: props.weaveRef,
    creator: null,
    feedback_type: STRUCTURED_FEEDBACK_TYPE,
    payload: {
      value,
      ref: props.feedbackSpecRef,
      name: props.structuredFeedbackOptions.name,
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
    weaveRef: props.weaveRef,
  });

  const [currentFeedbackId, setCurrentFeedbackId] = useState<string | null>(null);
  const [foundValue, setFoundValue] = useState<string | number | null>(null);
  const getTsClient = useGetTraceServerClientContext();

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
    const feedbackNameMatches = (feedback: any) => feedback.payload.name === props.structuredFeedbackOptions.name;
    const feedbackSpecMatches = (feedback: any) => feedback.payload.ref === props.feedbackSpecRef;

    const currFeedback = query.result?.find((feedback: any) => feedbackTypeMatches(feedback) && feedbackNameMatches(feedback) && feedbackSpecMatches(feedback));
    if (!currFeedback) {
        return;
    }

    setCurrentFeedbackId(currFeedback.id);
    setFoundValue(currFeedback?.payload?.value ?? null);
  }, [query?.result, query?.loading, props.feedbackSpecRef]);

  if (query?.loading) return <LoadingDots />;

  return (
    <div className="flex justify-center w-full">
      {renderFeedbackComponent()}
    </div>
  );

  function renderFeedbackComponent() {
    switch (props.structuredFeedbackOptions.type) {
      case FEEDBACK_TYPES.RANGE:
        return (
          <NumericalFeedbackColumn
            min={props.structuredFeedbackOptions.min}
            max={props.structuredFeedbackOptions.max}
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as number | null}
            currentFeedbackId={currentFeedbackId}
          />
        );
      case FEEDBACK_TYPES.CATEGORICAL:
        return (
          <CategoricalFeedbackColumn
            options={props.structuredFeedbackOptions.options}
            onAddFeedback={onAddFeedback}
            defaultValue={foundValue as string | null}
            currentFeedbackId={currentFeedbackId}
            multiSelect={props.structuredFeedbackOptions.multi_select}
            addNewOption={props.structuredFeedbackOptions.add_new_option}
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

// export const RangeFeedbackColumn = (
//     {min, max, onAddFeedback, defaultValue, currentFeedbackId}: 
//     {
//         min: number,
//         max: number, 
//         onAddFeedback?: (value: any, currentFeedbackId: string | null) => Promise<boolean>, 
//         defaultValue: number | null,
//         currentFeedbackId?: string | null,
//     }
// ) => {
//     const [value, setValue] = useState<number | undefined>(min ?? undefined);

//     useEffect(() => {
//         setValue(defaultValue ?? undefined);
//     }, [defaultValue]);


//     const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
//         // Todo debounce this
//         const val = parseInt(e.target.value);
//         onAddFeedback?.(val, currentFeedbackId ?? null).then((success) => {
//             if (success) {
//                 setValue(val);
//             }
//         });
//     }
        
//     return (
//     <Tailwind>
//         <div className="flex flex-col items-center w-full">
//             <span className="text-moon-500 mb-2">{value}</span>
//             <input
//                 type="range" 
//                 min={min} 
//                 max={max}
//                 step={1.0}
//                 value={value}
//                 onChange={onValueChange}
//                 className="w-full"
//             />
//         </div>
//     </Tailwind>
//     );
// }

export const NumericalFeedbackColumn = ({min, max, onAddFeedback, defaultValue, currentFeedbackId}: {min: number, max: number, onAddFeedback?: (value: number, currentFeedbackId: string | null) => Promise<boolean>, defaultValue: number | null, currentFeedbackId?: string | null}) => {
    const [value, setValue] = useState<number | undefined>(defaultValue ?? undefined);

    useEffect(() => {
        setValue(defaultValue ?? undefined);
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: number) => {
            onAddFeedback?.(val, currentFeedbackId ?? null);
        }, 500),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (v: string) => {
        const val = parseInt(v);
        setValue(val);
        debouncedOnAddFeedback(val);
    }

    return <div className='w-full'>
        <TextField
            type="number"
            value={value?.toString() ?? ''}
            onChange={onValueChange}
            placeholder='1000'
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
        }, 500),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (newValue: string) => {
        setValue(newValue);
        debouncedOnAddFeedback(newValue);
    }

    return <div className='w-full'>
        <TextField value={value} onChange={onValueChange} placeholder='Text'/>
    </div>
}

export const CategoricalFeedbackColumn = ({
    options, 
    onAddFeedback, 
    defaultValue, 
    currentFeedbackId,
    multiSelect,
    addNewOption
}: {
    options: string[], 
    onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, 
    defaultValue: string | null, 
    currentFeedbackId?: string | null,
    multiSelect: boolean,
    addNewOption: boolean
}) => {
    const [value, setValue] = useState<string>('');

    useEffect(() => {
        setValue(defaultValue ?? '');
    }, [defaultValue]);

    const debouncedOnAddFeedback = useCallback(
        debounce((val: string) => {
            onAddFeedback?.(val, currentFeedbackId ?? null);
        }, 500),
        [onAddFeedback, currentFeedbackId]
    );

    const onValueChange = (newValue: any) => {
        const val = newValue ? newValue.value : '';
        setValue(val);
        debouncedOnAddFeedback(val);
    }

    const dropdownOptions = options.map((option: string) => ({
        label: option,
        value: option,
    }));

    const customStyles = {
        control: (provided: any, state: any) => ({
            ...provided,
            backgroundColor: 'white',
            borderColor: state.isFocused ? '#007AFF' : '#E2E8F0',
            boxShadow: state.isFocused ? '0 0 0 1px #007AFF' : 'none',
            borderRadius: '8px',
            minHeight: '36px',
            width: '100%', // Make the select widget full width
            '&:hover': {
                borderColor: '#007AFF',
            },
        }),
        menu: (provided: any) => ({
            ...provided,
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            zIndex: 9999, // Ensure the dropdown appears above other elements
        }),
        option: (provided: any, state: any) => ({
            ...provided,
            backgroundColor: state.isSelected ? '#007AFF' : state.isFocused ? '#F0F0F0' : 'white',
            color: state.isSelected ? 'white' : '#333',
            '&:active': {
                backgroundColor: '#007AFF',
                color: 'white',
            },
        }),
        singleValue: (provided: any) => ({
            ...provided,
            color: '#333',
        }),
        input: (provided: any) => ({
            ...provided,
            color: '#333',
        }),
    };

    const SelectComponent = addNewOption ? CreatableSelect : Select;

    return (
        <Tailwind>
            <div className="flex justify-center w-full">
                <SelectComponent
                    styles={customStyles}
                    isClearable
                    isMulti={multiSelect}
                    onCreateOption={(inputValue: string) => {
                        return {label: inputValue, value: inputValue};
                    }}
                    onChange={onValueChange}
                    options={dropdownOptions}
                    value={dropdownOptions.find(option => option.value === value)}
                    menuPortalTarget={document.body}
                    menuPosition="fixed"
                    className="w-full" // Make the select component full width
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
        }, 500),
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
