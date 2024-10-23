
import { makeRefCall } from '@wandb/weave/util/refs';
import { z } from "zod";
import React, { useMemo } from 'react';

import { useWFHooks } from '../wfReactInterface/context';
import { CallSchema, ObjectVersionSchema } from '../wfReactInterface/wfDataModelHooksInterface';
import { parseRefMaybe } from '../../../Browse2/SmallRef';
import { objectVersionKeyToRefUri } from '../wfReactInterface/utilities';
import { useGetTraceServerClientContext } from '../wfReactInterface/traceServerClientContext';
import { projectIdFromParts } from '../wfReactInterface/tsDataModelHooks';

export const CallActionsViewer: React.FC<{
    call: CallSchema;
  }> = props => {
    const {artifactName, artifactVersion} = (parseRefMaybe(props.call.traceCall?.op_name ?? "") ?? {})
  const {useFeedback, useRootObjectVersions, useRefsData} = useWFHooks();
  const weaveRef = makeRefCall(props.call.entity, props.call.project, props.call.callId);
  const feedbackQuery = useFeedback({
    entity: props.call.entity, 
    project: props.call.project,
    weaveRef,
  });
  const allActions = useRootObjectVersions(   props.call.entity, 
    props.call.project,{
        baseObjectClasses: ['ActionOpMapping'],
        latestOnly: true,
  })
  console.log(allActions.result)

  type BuiltinAction = {
        "action_type": "builtin",
        "name": string,
        "digest": string
    }

  type ActionWithConfig = {
    "_type": "ActionWithConfig";
    "name": string;
    "action": BuiltinAction;
    "config": Record<string, unknown>;
    }


    const verifiedActions: {data: ActionOpMapping, action:ObjectVersionSchema}[] = useMemo(() => {
        return (allActions.result ?? []).map(
            action =>{const res = ActionOpMappingZ.safeParse(action.val); console.log(res); return {data:res.data, action}}
        ).filter(({data}) => {
            return data?.op_name === artifactName && (data?.op_digest === artifactVersion || data?.op_digest === "*")
        }) as {data: ActionOpMapping, action:ObjectVersionSchema}[]
    }, [allActions.result, artifactName, artifactVersion])

    const verifiedActionFeedbacks: ActionFeedback[] = useMemo(() => {
        return (feedbackQuery.result ?? []).map(
            feedback =>{const res = ActionFeedbackZ.safeParse(feedback.payload); console.log(res); return res}
        ).filter(result => result.success).map(result => result.data)
    }, [feedbackQuery.result])

    console.log({verifiedActions, verifiedActionFeedbacks})

    const getFeedbackForAction = (actionRef: string) => {
        console.log({verifiedActionFeedbacks, actionRef})
        return verifiedActionFeedbacks.filter(feedback => feedback.action_mapping_ref === actionRef)
    }

    
    const getClient = useGetTraceServerClientContext()


    return <table>
        <thead>
            <tr>
                <th>Action</th>
                <th>Run Count</th>
                <th>Last Result</th>
                <th>Run</th>
            </tr>
        </thead>
        <tbody>
            {verifiedActions.map(({data, action}) => {
                const mappingRef = objectVersionKeyToRefUri(action)
                const feedbacks = getFeedbackForAction(mappingRef)
                return <tr key={mappingRef}>
                    <td>{data.name}</td>
                    <td>{feedbacks.length}</td>
                    <td>{feedbacks.length > 0 ? JSON.stringify(feedbacks[0].results) : "N/A"}</td>
                    <td><button onClick={() => {
                        getClient().executeBatchAction({
                            project_id: projectIdFromParts({
                                entity: props.call.entity,
                                project: props.call.project,
                            }),
                            call_ids: [props.call.callId],
                            mapping_ref: mappingRef,
                        }).then(res => {
                            feedbackQuery.refetch()
                        })
                    }}>Run</button></td>
                </tr>
            })}
        </tbody>
    </table>

  }


const ActionOpMappingZ = z.object({
  _type: z.literal("ActionOpMapping"),
  name: z.string(),
  action: z.string(),
  op_name: z.string(),
  op_digest: z.string(),
  input_mapping: z.record(z.string(), z.string()),
});

type ActionOpMapping = z.infer<typeof ActionOpMappingZ>;

const ActionFeedbackZ = z.object({
    // _type: z.literal("ActionFeedback"),
    name: z.string(),
    action_mapping_ref: z.string(),
    results: z.record(z.string(), z.unknown()),
})

type ActionFeedback = z.infer<typeof ActionFeedbackZ>;