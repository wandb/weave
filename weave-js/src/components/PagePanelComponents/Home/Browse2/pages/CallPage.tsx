import React, {useMemo} from 'react';
import {Browse2TraceComponent} from '../Browse2TracePage';
import {useWeaveflowORMContext} from './interface/wf/context';

export const CallPage: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const orm = useWeaveflowORMContext();
  const params = useMemo(() => {
    return {
      entity: props.entity,
      project: props.project,
      traceId: orm.projectConnection.call(props.callId).traceID(),
      spanId: props.callId,
    };
  }, [orm.projectConnection, props.callId, props.entity, props.project]);
  return <Browse2TraceComponent params={params} />;
};

// {/* <div>
//       <h1>CallPage Placeholder</h1>
//       <div>
//         This is the <strong>TRACE VIEW PAGE!! YAY</strong>. A lot of work has
//         been done on this page already. But essentially, this is the call detail
//         page (which implicitly should show the trace as well.)
//       </div>
//       <div>Migration Notes:</div>
//       <ul>
//         <li>
//           Weaveflow already has a great starting point for this page (eg.
//           <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/trace/c54d4067-a0f2-43a2-8fdb-dc8bd5fc40c0/2f7b8cd9-712b-421b-b1c8-f803ee3679a4">
//             https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/trace/c54d4067-a0f2-43a2-8fdb-dc8bd5fc40c0/2f7b8cd9-712b-421b-b1c8-f803ee3679a4
//           </a>
//         </li>
//       </ul>
//       <div>Primary Features:</div>
//       <ul>
//         <li>
//           Trace View! - This should be able to filter down to just the stack for
//           simplicity. Ideally the trace view is tabular in nature and allows the
//           user to see inputs and outputs of many calls at once.
//         </li>
//         <li>Input Data</li>
//         <li>Output Data</li>
//         <li>Can Add Feedback</li>
//         <li>Can add to Dataset</li>
//       </ul>
//       <div>Links:</div>
//       <ul>
//         <li>
//           Can link to the input ObjectVersion:{' '}
//           <Link to={prefix('/objects/object_name/versions/version_id')}>
//             /object/object_name/versions/version_id
//           </Link>
//         </li>
//         <li>
//           Can link to the output ObjectVersion:{' '}
//           <Link to={prefix('/objects/object_name/versions/version_id')}>
//             /object/object_name/versions/version_id
//           </Link>
//         </li>
//         <li>
//           Can link to the associated OpVersion:{' '}
//           <Link to={prefix('/ops/op_name/versions/version_id')}>
//             /ops/op_name/versions/version_id
//           </Link>
//         </li>
//       </ul>
//       <div>Inspiration</div>
//       This page will basically be a simple table of Op Versions, with some
//       lightweight filtering on top.
//       <br />
//       <img
//         src="https://github.com/wandb/weave/blob/a0d44639b972421890ed6149f9cbc01211749291/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/call_example.png?raw=true"
//         style={{
//           width: '100%',
//         }}
//         alt=""
//       />
//     </div> */}
