import {Box, TextField, Typography} from '@material-ui/core';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {useMemo} from 'react';
import {Button} from 'semantic-ui-react';

import {Browse2OpDefCode} from '../Browse2OpDefCode';
import {StreamId} from '../callTree';
import {
  useFirstCall,
  useOpSignature,
  useRunsWithFeedback,
} from '../callTreeHooks';
import {Paper} from '../CommonLib';
import {RunsTable} from '../RunsTable';
import {
  ScrollableTabContent,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {CallsTable} from './CallsPage';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  version: string;
}> = props => {
  // const prefix = useEPPrefix();
  const orm = useWeaveflowORMContext();
  const opVersion = orm.projectConnection.opVersion(
    props.opName,
    props.version
  );
  const uri = opVersion.refUri();
  const streamId = useMemo(
    () => ({
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    }),
    [props.entity, props.project]
  );

  return (
    <SimplePageLayout
      title={props.opName + ' : ' + props.version}
      tabs={[
        {
          label: 'Calls',
          content: (
            <CallsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={{
                opVersions: [props.opName + ':' + props.version],
                traceRootsOnly: false,
              }}
            />
          ),
        },

        {
          label: 'Execute',
          content: (
            <ScrollableTabContent>
              <OpVersionExecute streamId={streamId} uri={uri} />
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Code',
          content: (
            <ScrollableTabContent>
              <Browse2OpDefCode uri={uri} />
            </ScrollableTabContent>
          ),
        },
        {label: 'DAG', content: <div>DAG</div>},
      ]}
    />
  );
  // return ;
};

const OpVersionExecute: React.FC<{
  streamId: StreamId;
  uri: string;
}> = ({streamId, uri}) => {
  const firstCall = useFirstCall(streamId, uri);
  const opSignature = useOpSignature(streamId, uri);
  return (
    <Paper>
      <Typography variant="h6" gutterBottom>
        Call Op
      </Typography>
      <Box sx={{width: 400}}>
        {opSignature.result != null &&
          Object.keys(opSignature.result.inputTypes).map(k => (
            <Box key={k} mb={2}>
              <TextField
                label={k}
                fullWidth
                value={
                  firstCall.result != null
                    ? firstCall.result.inputs[k]
                    : undefined
                }
              />
            </Box>
          ))}
      </Box>
      <Box pt={1}>
        <Button variant="outlined" sx={{backgroundColor: globals.lightYellow}}>
          Execute
        </Button>
      </Box>
    </Paper>
  );
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
