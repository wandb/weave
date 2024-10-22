import React, { SyntheticEvent, useState } from 'react';
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

    const getTsClient = useGetTraceServerClientContext();

    const onAddFeedback = (value: string) => {
        console.log("onAddFeedback", value);
        const req = {
          project_id: `${entity}/${project}`,
          weave_ref: weaveRef,
          creator: null,
          feedback_type: 'wandb.structuredFeedback.1',
          payload: {value},
          sort_by: [{"created_at": "desc"}]
        };
        getTsClient().feedbackCreate(req);
      };

    const foundValue = query?.result?.find((feedback: any) => feedback.feedback_type === 'wandb.structuredFeedback.1')?.payload?.value;

    if (query?.loading) {
        return <LoadingDots />;
    }
     
    if (structuredFeedbackOptions.type === 'RangeFeedback') {
        return <RangeFeedbackColumn min={structuredFeedbackOptions.min} max={structuredFeedbackOptions.max} onAddFeedback={onAddFeedback} defaultValue={foundValue}/>;
    } else if (structuredFeedbackOptions.type === 'CategoricalFeedback') {
        return <CategoricalFeedbackColumn options={structuredFeedbackOptions.options} onAddFeedback={onAddFeedback} defaultValue={foundValue ?? undefined}/>;
    }
  return <div>unknown feedback type</div>;
};


export const RangeFeedbackColumn = ({min, max, onAddFeedback, defaultValue}: {min: number, max: number, onAddFeedback?: (value: string) => void, defaultValue: string | null}) => {

    const [value, setValue] = useState(defaultValue ?? min);

    const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        //Todo debounce this
        setValue(e.target.value);
        onAddFeedback?.(e.target.value);
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

export const CategoricalFeedbackColumn = ({options, onAddFeedback, defaultValue}: {options: string[], onAddFeedback?: (value: string) => void, defaultValue: string | null}) => {
    let foundValue = defaultValue;
    if (defaultValue && !options.includes(defaultValue)) {
        console.log("structured column version mismatch, option not found", defaultValue, options);
        foundValue = null;
    }
    
    const [value, setValue] = useState<string>(foundValue ?? '');

    const onValueChange = (e: SyntheticEvent<HTMLSelectElement>) => {
        const val = (e.target as HTMLSelectElement).value;
        if (val) {
            setValue(val);
            onAddFeedback?.(val);
        } else {
            // handle delete req?
            setValue(val);
            onAddFeedback?.(val);
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
