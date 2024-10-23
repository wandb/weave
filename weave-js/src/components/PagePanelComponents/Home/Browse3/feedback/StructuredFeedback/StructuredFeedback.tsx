import React, { SyntheticEvent, useEffect, useState } from 'react';
import { useWFHooks } from '../../pages/wfReactInterface/context';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { LoadingDots } from '@wandb/weave/components/LoadingDots';
import Select from 'react-select'
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { Checkbox } from '@mui/material';
import CreatableSelect from 'react-select/creatable';

export const StructuredFeedbackCell = ({structuredFeedbackOptions, callId, weaveRef, entity, project, feedbackSpecRef}: {structuredFeedbackOptions: any, callId: string, weaveRef: string, entity: string, project: string, feedbackSpecRef: string}) => {

    const {useFeedback} = useWFHooks();
    const query = useFeedback(
        {
        entity,
        project,
        weaveRef,
        },
    );

    const [currentFeedbackId, setCurrentFeedbackId] = useState<string | null>(null);
    const [foundValue, setFoundValue] = useState<string | number | null>(null);
    const getTsClient = useGetTraceServerClientContext();

    const onAddFeedback = (value: any, currentFeedbackId: string | null): Promise<boolean> => {
        console.log("onAddFeedback", value, currentFeedbackId);
        const req = {
          project_id: `${entity}/${project}`,
          weave_ref: weaveRef,
          creator: null,
          feedback_type: 'wandb.structuredFeedback.1',
          payload: {
            value,
            ref: feedbackSpecRef,
          },
          sort_by: [{"created_at": "desc"}]
        };
        if (currentFeedbackId) {
            const replaceReq = {...req, feedback_id: currentFeedbackId};
            return getTsClient().feedbackReplace(replaceReq).then((res) => {
                console.log("feedback replace res", res);
                if (res.reason) {
                    console.error("feedback replace failed", res.reason);
                }
                if (res.id) {
                    setCurrentFeedbackId(res.id);
                    return true;
                }
                return false;
            });
        } else {
            return getTsClient().feedbackCreate(req).then((res) => {
                console.log("feedback create res", res);
                if (res.id) {
                    setCurrentFeedbackId(res.id);
                    return true;
                }
                return false;
            });
        }
      };

    useEffect(() => {
        if (query?.loading) {
            return;
        }
        const currFeedback = query.result?.find((feedback: any) => feedback.feedback_type === 'wandb.structuredFeedback.1');
        if (!currFeedback) {
            return
        }
        if (currFeedback.payload.ref !== feedbackSpecRef) {
            return;
        }
        setCurrentFeedbackId(currFeedback.id);
        setFoundValue(currFeedback?.payload?.value ?? null);
    }, [query?.result, query?.loading, setCurrentFeedbackId, setFoundValue]);

    if (query?.loading) {
        return <LoadingDots />;
    }

    if (!structuredFeedbackOptions.editable) {
        return <div>{foundValue}</div>
    }

    // console.log(structuredFeedbackOptions, query?.result?.find((feedback: any) => feedback.feedback_type === 'wandb.structuredFeedback.1'))
     
    if (structuredFeedbackOptions.type === 'RangeFeedback') {
        return <RangeFeedbackColumn min={structuredFeedbackOptions.min} max={structuredFeedbackOptions.max} onAddFeedback={onAddFeedback} defaultValue={foundValue} currentFeedbackId={currentFeedbackId} editable={structuredFeedbackOptions.editable} />;
    } else if (structuredFeedbackOptions.type === 'CategoricalFeedback') {
        return <CategoricalFeedbackColumn 
            options={structuredFeedbackOptions.options} 
            onAddFeedback={onAddFeedback} 
            defaultValue={foundValue} 
            currentFeedbackId={currentFeedbackId}
            multiSelect={structuredFeedbackOptions.multi_select}
            addNewOption={structuredFeedbackOptions.add_new_option}
            editable={structuredFeedbackOptions.editable}
        />;
    } else if (structuredFeedbackOptions.type === 'BinaryFeedback') {
        return <BinaryFeedbackColumn 
            onAddFeedback={onAddFeedback} 
            defaultValue={foundValue} 
            currentFeedbackId={currentFeedbackId}
            editable={structuredFeedbackOptions.editable}
        />;
    }
  return <div>unknown feedback type</div>;
};


export const RangeFeedbackColumn = (
    {min, max, onAddFeedback, defaultValue, currentFeedbackId, editable}: 
    {
        min: number,
        max: number, 
        onAddFeedback?: (value: any, currentFeedbackId: string | null) => Promise<boolean>, 
        defaultValue: string | null,
        currentFeedbackId: string | null,
        editable: boolean
    }
) => {
    const [value, setValue] = useState<any | null>(min);

    useEffect(() => {
        if (defaultValue) {
            setValue(defaultValue);
        }
    }, [defaultValue]);


    const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // Todo debounce this
        const val = parseInt(e.target.value);
        onAddFeedback?.(val, currentFeedbackId).then((success) => {
            if (success) {
                setValue(val);
            }
        });
    }
        
    return (
    <Tailwind>
        <div className="flex">
            <span className="text-moon-500 mr-4">{value}</span>
            <input
                type="range" 
                min={min} 
                max={max}
                step={1.0}
                value={value}
                onChange={onValueChange} 
                disabled={!editable && defaultValue != null}
            />
        </div>
    </Tailwind>
    );
}

export const CategoricalFeedbackColumn = ({
    options, 
    onAddFeedback, 
    defaultValue, 
    currentFeedbackId,
    multiSelect,
    addNewOption,
    editable
}: {
    options: string[], 
    onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, 
    defaultValue: string | null, 
    currentFeedbackId: string | null,
    multiSelect: boolean,
    addNewOption: boolean,
    editable: boolean
}) => {
    let foundValue = defaultValue;
    if (defaultValue && !options.includes(defaultValue)) {
        console.log("structured column version mismatch, option not found", defaultValue, options);
        foundValue = null;
    }
    
    const [value, setValue] = useState<string>('');

    useEffect(() => {
        if (foundValue) {
            setValue(foundValue);
        }
    }, [foundValue]);

    const onValueChange = (newValue: any) => {
        const val = newValue ? newValue.value : '';
        onAddFeedback?.(val, currentFeedbackId).then((success) => {
            if (success) {
                setValue(val);
            }
        });
    }

    const dropdownOptions = options.map((option: string) => ({
        label: option,
        value: option,
    }));

    const controlStyles = {
        base: "border rounded-lg bg-white hover:cursor-pointer max-w-full h-10 max-h-10",
        focus: "border-primary-600 ring-1 ring-primary-500",
        nonFocus: "border-gray-300 hover:border-gray-400",
      };

    return (
        <Tailwind>
            <div className="flex flex-col justify-center items-center bg-moon-100">
                {addNewOption === true ? (
                    <CreatableSelect
                        classNames={{
                            control:  ({ isFocused }) =>
                                `isFocused ? ${controlStyles.focus} : ${controlStyles.nonFocus} ${controlStyles.base}`,
                        }}
                        isClearable
                        isMulti={multiSelect}
                        onCreateOption={(inputValue: string) => {
                            return {label: inputValue, value: inputValue};
                        }}
                        onChange={onValueChange}
                        options={dropdownOptions}
                        value={dropdownOptions.find(option => option.value === value)}
                        isDisabled={!editable && defaultValue != null}
                    />
                ) : (
                    <Select
                        onChange={onValueChange}
                        options={dropdownOptions}
                        value={dropdownOptions.find(option => option.value === value)}
                        classNames={{
                            control: ({ isFocused }) =>
                                `isFocused ? ${controlStyles.focus} : ${controlStyles.nonFocus} ${controlStyles.base}`,
                        }}
                        isDisabled={!editable && defaultValue != null}
                    />
                )} 
            </div>
        </Tailwind>
    );
}

export const BinaryFeedbackColumn = ({onAddFeedback, defaultValue, currentFeedbackId, editable}: {onAddFeedback?: (value: string, currentFeedbackId: string | null) => Promise<boolean>, defaultValue: string | null, currentFeedbackId: string | null, editable: boolean}) => {
    // Checkbox
    const [value, setValue] = useState<boolean | null>(defaultValue);

    const onValueChange = (e: SyntheticEvent<HTMLInputElement>) => {
        const val = (e.target as HTMLInputElement).checked ? 'true' : 'false';
        onAddFeedback?.(val, currentFeedbackId).then((success) => {
            if (success) {
                setValue(val === 'true');
            }
        });
    }

    return <Tailwind>
        <Checkbox checked={value ?? false} onChange={onValueChange} disabled={!editable && defaultValue != null}/>
    </Tailwind>
}
