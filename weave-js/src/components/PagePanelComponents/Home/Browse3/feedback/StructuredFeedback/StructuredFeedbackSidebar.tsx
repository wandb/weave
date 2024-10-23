import React from 'react';
import { StructuredFeedbackCell } from './StructuredFeedback';
import { makeRefCall } from '@wandb/weave/util/refs';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { useStructuredFeedbackOptions } from '../../pages/CallsPage/CallsTable';

export default function StructuredFeedbackSidebar(
    props: {
        entity: string,
        project: string,
        callID: string,
        nextCall: () => void,
    }
) {
    const feedbackOptions = useStructuredFeedbackOptions(props.entity, props.project);
    const types = feedbackOptions?.types;
    const feedbackSpecRef = feedbackOptions?.ref;
    const weaveRef = makeRefCall(props.entity, props.project, props.callID);

    return (
        <Tailwind>
            <div className='flex flex-col h-full bg-white'>
                <div className='flex-grow overflow-y-auto'>
                    {types?.map((type: any) => (
                        <div className='border-b border-gray-200 last:border-b-0' key={type.name}>
                            <h3 className='px-4 py-3 text-sm font-semibold text-gray-700 bg-gray-50'>{type.name}</h3>
                            <div className='p-4'>
                                <StructuredFeedbackCell
                                    feedbackSpecRef={feedbackSpecRef}
                                    weaveRef={weaveRef}
                                    structuredFeedbackOptions={type}
                                    entity={props.entity}
                                    project={props.project}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </Tailwind>
    );
}
