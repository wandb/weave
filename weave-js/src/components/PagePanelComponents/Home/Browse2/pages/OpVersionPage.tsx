import React, {useMemo} from 'react';

import {Browse2OpDefComponent} from '../Browse2OpDefPage';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  digest: string;
}> = props => {
  // const prefix = useEPPrefix();
  const params = useMemo(() => {
    return {
      entity: props.entity,
      project: props.project,
      rootType: '',
      objName: props.opName,
      objVersion: props.digest,
    };
  }, [props]);
  return <Browse2OpDefComponent params={params} />;
};

// <div>
// <h1>OpVersionPage Placeholder</h1>
// <div>
//   This is the detail page for OpVersion. An OpVersion is a "version" of a
//   weave "op". In the user's mind it is analogous to a specific
//   implementation of a method.
// </div>
// <div>Migration Notes:</div>
// <ul>
//   <li>
//     Weaveflow already has a goode starting point for this page (eg.{' '}
//     <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/OpDef/OpenaiChatModel-complete/ecbdfcda78f8e7ce214b">
//       https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/OpDef/OpenaiChatModel-complete/ecbdfcda78f8e7ce214b
//     </a>
//     )
//   </li>
// </ul>
// <div>Primary Features:</div>
// <ul>
//   <li>Code</li>
//   <li>(future) Type/OpDef DAG Visual</li>
// </ul>
// <div>Links:</div>
// <ul>
//   <li>
//     Link to all types in type stub (consuming and producing) ({' '}
//     <Link to={prefix('/types/type_name')}>/types/[type_name]</Link>)
//   </li>
//   <li>
//     Connection to all calls for this op version ({' '}
//     <Link to={prefix('/calls?filter=from_op=op_name:version')}>
//       /calls?filter=from_op=op_name:version
//     </Link>
//     )
//   </li>
// </ul>
// <div>Inspiration</div>
// Existing Weaveflow page:
// <br />
// <img
//   src="https://github.com/wandb/weave/blob/96665d8a25dd9d7d0aaa9cde2bd5e80c1520e491/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/opversion_example.png?raw=true"
//   style={{
//     width: '100%',
//   }}
//   alt=""
// />
// </div>
