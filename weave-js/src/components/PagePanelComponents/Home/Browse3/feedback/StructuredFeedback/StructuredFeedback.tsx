import React, { SyntheticEvent, useEffect, useState } from 'react';
import { useWFHooks } from '../../pages/wfReactInterface/context';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { LoadingDots } from '@wandb/weave/components/LoadingDots';
import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import { DropdownProps } from 'semantic-ui-react';
import Select, { StylesConfig } from 'react-select'
import { Tailwind } from '@wandb/weave/components/Tailwind';

export const StructuredFeedbackColumn = ({structuredFeedbackOptions, callId, weaveRef, entity, project}: {structuredFeedbackOptions: any, callId: string, weaveRef: string, entity: string, project: string}) => {

    const {useFeedback} = useWFHooks();
    const query = useFeedback(
        {
        entity,
        project,
        weaveRef,
        },
    );

    const [currentFeedbackId, setCurrentFeedbackId] = useState<string | null>(null);
    const [foundValue, setFoundValue] = useState<string | null>(null);
    const getTsClient = useGetTraceServerClientContext();

    const onAddFeedback = (value: string, currentFeedbackId: string | null): boolean => {
        console.log("onAddFeedback", value, currentFeedbackId);
        const req = {
          project_id: `${entity}/${project}`,
          weave_ref: weaveRef,
          creator: null,
          feedback_type: 'wandb.structuredFeedback.1',
          payload: {value},
          sort_by: [{"created_at": "desc"}]
        };
        if (currentFeedbackId) {
            const replaceReq = {...req, feedback_id: currentFeedbackId};
            getTsClient().feedbackReplace(replaceReq).then((res) => {
                console.log("feedback replaced", res);
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
            getTsClient().feedbackCreate(req).then((res) => {
                console.log("feedback created", res);
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
        setCurrentFeedbackId(currFeedback.id);
        setFoundValue(currFeedback?.payload?.value ?? null);
    }, [query?.result, query?.loading, setCurrentFeedbackId, setFoundValue]);

    if (query?.loading) {
        return <LoadingDots />;
    }
     
    if (structuredFeedbackOptions.type === 'RangeFeedback') {
        return <RangeFeedbackColumn min={structuredFeedbackOptions.min} max={structuredFeedbackOptions.max} onAddFeedback={onAddFeedback} defaultValue={foundValue} currentFeedbackId={currentFeedbackId}/>;
    } else if (structuredFeedbackOptions.type === 'CategoricalFeedback') {
        return <CategoricalFeedbackColumn options={structuredFeedbackOptions.options} onAddFeedback={onAddFeedback} defaultValue={foundValue} currentFeedbackId={currentFeedbackId}/>;
    }
  return <div>unknown feedback type</div>;
};


export const RangeFeedbackColumn = (
    {min, max, onAddFeedback, defaultValue, currentFeedbackId}: 
    {
        min: number,
        max: number, 
        onAddFeedback?: (value: string, currentFeedbackId: string | null) => boolean, 
        defaultValue: string | null,
        currentFeedbackId: string | null
    }
) => {

    const [value, setValue] = useState(defaultValue ?? min);

    const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        //Todo debounce this
        const success = onAddFeedback?.(e.target.value, currentFeedbackId);
        if (success) {
            setValue(e.target.value);
        }
    }
    
    return (
    <Tailwind>
        <div className="flex">
            <span className="text-moon-500 mr-4">{min}</span>
            <input 
                type="range" 
                min={min} 
                max={max}
                step={(max - min) / 100}
                value={value} 
                onChange={onValueChange} 
            />
            <span className="text-moon-500 ml-4">{max}</span>
        </div>
        {/* <input 
            type="range" 
            min={min} 
            max={max}
            step={(max - min) / 100}
            value={value} 
            onChange={onValueChange} 
        /> */}
    </Tailwind>
    );
}

export const CategoricalFeedbackColumn = ({options, onAddFeedback, defaultValue, currentFeedbackId}: {options: string[], onAddFeedback?: (value: string, currentFeedbackId: string | null) => void, defaultValue: string | null, currentFeedbackId: string | null}) => {
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

    const onValueChange = (e: SyntheticEvent<HTMLSelectElement>) => {
        const val = (e.target as HTMLSelectElement).value;
        if (val) {
            setValue(val);
            onAddFeedback?.(val, currentFeedbackId);
        } else {
            // handle delete req?
            setValue(val);
            onAddFeedback?.(val, currentFeedbackId);
        }
    }

    const dropdownOptions = options.map((option: string) => ({
        text: option,
        value: option,
    }));
    dropdownOptions.push({text: '', value: ''});

    return (
        <Tailwind>
            <div className="flex flex-col justify-center items-center bg-moon-100">
                <select onChange={onValueChange} value={value} className='w-full bg-moon-100'>
                    {dropdownOptions.map((option: any) => (
                        <option key={option.value} value={option.value}>{option.text}</option>
                    ))}
                </select>
            </div>
        </Tailwind>
    );
}
