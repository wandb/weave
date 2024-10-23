import React, { useState } from 'react';
import { StructuredFeedbackCell } from './StructuredFeedback';
import { CallSchema } from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import { makeRefCall, makeRefObject } from '@wandb/weave/util/refs';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import {  ConfigureStructuredFeedbackModal } from './AddColumnButton';
import { Button } from '@wandb/weave/components/Button';
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
    const feedbackSpecRef = feedbackOptions?.ref
    const weaveRef = makeRefCall(props.entity, props.project, props.callID);

    return (
        <Tailwind>
            <div className='flex flex-col h-full'>
                <div className='flex-grow'>
                    {types?.map((type: any) => {
                        return (
                            <div className='p-8' key={type.name}>
                                <h3>{type.name}</h3>
                                <div className='flex flex-col gap-2'>
                                    <StructuredFeedbackCell feedbackSpecRef={feedbackSpecRef} weaveRef={weaveRef} structuredFeedbackOptions={type} entity={props.entity} project={props.project}/>
                                </div>
                            </div>
                        )
                    })}
                </div>
                <div className='flex justify-center p-8 mt-auto'>
                    <Button onClick={props.nextCall}>Next call</Button>
                </div>
            </div>
        </Tailwind>
    )
}
