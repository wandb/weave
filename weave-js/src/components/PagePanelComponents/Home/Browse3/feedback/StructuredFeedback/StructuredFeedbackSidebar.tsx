
import React from 'react';
import { StructuredFeedbackCell } from './StructuredFeedback';
import { CallSchema } from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import { makeRefCall } from '@wandb/weave/util/refs';
import { Tailwind } from '@wandb/weave/components/Tailwind';

export default function StructuredFeedbackSidebar(
    props: {
        call: CallSchema,
        structuredFeedbackOptions: any,
    }
) {
    const weaveRef = makeRefCall(props.call.entity, props.call.project, props.call.callId);
    const types = props.structuredFeedbackOptions.types;

    return (
        <Tailwind>
            {types.map((type: any) => {
                return (
                    <div className='p-8'>
                        <h3>{type.name ?? type.type}</h3>
                        <div className='flex flex-col gap-2'>
                            <StructuredFeedbackCell feedbackSpecRef={props.structuredFeedbackOptions.ref} structuredFeedbackOptions={type} callId={props.call.callId} weaveRef={weaveRef} entity={props.call.entity} project={props.call.project}/>
                        </div>
                    </div>
                )
            })}
        </Tailwind>
    )
}