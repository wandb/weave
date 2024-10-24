import React, { useState } from 'react';
import { StructuredFeedbackCell } from './StructuredFeedback';
import { makeRefCall } from '@wandb/weave/util/refs';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { useStructuredFeedbackOptions } from '../../pages/CallsPage/CallsTable';
import { Button } from '../../../../../Button/Button';
import { Icon } from '../../../../../Icon';

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
    const [isExpanded, setIsExpanded] = useState(true);

    const feedbackCount = types?.length ?? 0;

    return (
        <Tailwind>
            <div className='flex flex-col h-full bg-white'>
                <div className='p-12 border-b border-moon-300 w-full flex justify-center'>
                    <h2 className='text-lg font-semibold text-gray-900'>Add feedback</h2>
                </div>
                <div className='mx-6 flex-grow h-full'>
                    <div>
                        <button
                            className='w-full px-6 py-8 flex items-center justify-between text-md font-semibold text-gray-700 hover:bg-gray-100'
                            onClick={() => setIsExpanded(!isExpanded)}
                        >
                            <div className='flex items-center'>
                                <span className=''>Human scores</span>
                                <span className='ml-2 px-2 py-1 text-xs font-medium text-gray-600 bg-gray-200 rounded-full'>
                                    {feedbackCount}
                                </span>
                            </div>
                            <Icon name={isExpanded ? 'chevron-up' : 'chevron-down'} />
                        </button>
                        {isExpanded && (
                            <div>
                                {types?.map((type: any) => (
                                    <div key={type.name}>
                                        <h3 className='px-6 py-4 text-sm font-semibold text-gray-700 bg-gray-50'>{type.name}</h3>
                                        <div className='px-6 pt-2 pb-8'>
                                            <StructuredFeedbackCell
                                                feedbackSpecRef={feedbackSpecRef}
                                                weaveRef={weaveRef}
                                                structuredFeedbackOptions={type}
                                                entity={props.entity}
                                                project={props.project}
                                                readOnly={false}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
                <div className='p-6 border-t border-moon-300 sticky bottom-0 bg-white'>
                    <Button
                        onClick={props.nextCall}
                        className='w-full'
                        color='primary'
                    >
                        Done
                    </Button>
                </div>
            </div>
        </Tailwind>
    );
}
