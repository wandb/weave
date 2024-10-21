import React, { SyntheticEvent, useState } from 'react';
import { useWFHooks } from '../pages/wfReactInterface/context';
import { useGetTraceServerClientContext } from '../pages/wfReactInterface/traceServerClientContext';
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
        };
        getTsClient().feedbackCreate(req);
      };

    const foundValue = query?.result?.find((feedback: any) => feedback.feedback_type === 'wandb.structuredFeedback.1')?.payload?.value;

    if (query?.loading) {
        return <LoadingDots />;
    }

    console.log("foundValue", foundValue);
     
    if (structuredFeedbackOptions.type === 'RangeFeedback') {
        return <RangeFeedbackColumn structuredFeedbackOptions={structuredFeedbackOptions} onAddFeedback={onAddFeedback} defaultValue={foundValue}/>;
    } else if (structuredFeedbackOptions.type === 'CategoricalFeedback') {
        return <CategoricalFeedbackColumn structuredFeedbackOptions={structuredFeedbackOptions} onAddFeedback={onAddFeedback} defaultValue={foundValue ?? undefined}/>;
    }
  return <div>unknown feedback type</div>;
};


const RangeFeedbackColumn = ({structuredFeedbackOptions, onAddFeedback, defaultValue}: {structuredFeedbackOptions: any, onAddFeedback: (value: string) => void, defaultValue: string | null}) => {

    const [value, setValue] = useState(defaultValue ?? structuredFeedbackOptions.min);

    const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        //Todo debounce this
        setValue(e.target.value);
        onAddFeedback(e.target.value);
    }
    
    return (
    <div>
        <input 
            type="range" 
            min={structuredFeedbackOptions.min} 
            max={structuredFeedbackOptions.max}
            step={(structuredFeedbackOptions.max - structuredFeedbackOptions.min) / 100}
            value={value} 
            onChange={onValueChange} 
        />
    </div>
    );
}

const CategoricalFeedbackColumn = ({structuredFeedbackOptions, onAddFeedback, defaultValue}: {structuredFeedbackOptions: any, onAddFeedback: (value: string) => void, defaultValue: string | null}) => {
    const [value, setValue] = useState<string>(defaultValue ?? '');

    const onValueChange = (e: SyntheticEvent<HTMLSelectElement>) => {
        const val = (e.target as HTMLSelectElement).value;
        if (val) {
            setValue(val);
            onAddFeedback(val);
        } else {
            // handle delete req?
        }
    }

    const options = structuredFeedbackOptions.options.map((option: string) => ({
        text: option,
        value: option,
    }));
    options.push({text: '', value: ''});

    return (
        <Tailwind>
            <div className="flex flex-col justify-center items-center bg-moon-100">
                <select onChange={onValueChange} value={value} className='w-full bg-moon-100'>
                    {options.map((option: any) => (
                        <option key={option.value} value={option.value}>{option.text}</option>
                    ))}
                </select>
            </div>
        </Tailwind>
    );
}
