import {Box, TextField, Typography} from '@material-ui/core';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {useMemo} from 'react';
import {Button} from 'semantic-ui-react';

import {Browse2OpDefCode} from '../Browse2OpDefCode';
import {StreamId} from '../callTree';
import {useFirstCall, useOpSignature} from '../callTreeHooks';
import {Paper} from '../CommonLib';
import {CallsTable} from './CallsPage';
import {OpLink, OpVersionLink, TypeVersionLink} from './common/Links';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFOpVersion} from './interface/wf/types';
import {FilterableOpVersionsTable} from './OpVersionsPage';

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
          label: 'Overview',
          content: (
            <ScrollableTabContent>
              <SimpleKeyValueTable
                data={{
                  Name: <OpLink opName={props.opName} />,
                  Category: (
                    <OpVersionCategoryChip
                      opCategory={opVersion.opCategory()}
                    />
                  ),
                  Version: props.version,
                  'Input Types': (
                    <ul style={{margin: 0}}>
                      {opVersion.inputTypesVersions().map((t, i) => (
                        <li key={i}>
                          <TypeVersionLink
                            typeName={t.type().name()}
                            version={t.version()}
                          />
                        </li>
                      ))}
                    </ul>
                  ),
                  'Output Types': (
                    <ul style={{margin: 0}}>
                      {opVersion.outputTypeVersions().map((t, i) => (
                        <li key={i}>
                          <TypeVersionLink
                            typeName={t.type().name()}
                            version={t.version()}
                          />
                        </li>
                      ))}
                    </ul>
                  ),
                  'Call Tree': <OpVersionOpTree opVersion={opVersion} />,
                }}
              />
            </ScrollableTabContent>
          ),
        },
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
          label: 'Invokes',
          content: (
            <FilterableOpVersionsTable
              entity={opVersion.entity()}
              project={opVersion.project()}
              frozenFilter={{
                invokedByOpVersions: [
                  opVersion.op().name() + ':' + opVersion.version(),
                ],
              }}
            />
          ),
        },
        {
          label: 'Invoked By',
          content: (
            <FilterableOpVersionsTable
              entity={opVersion.entity()}
              project={opVersion.project()}
              frozenFilter={{
                invokesOpVersions: [
                  opVersion.op().name() + ':' + opVersion.version(),
                ],
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
        {
          label: 'DAG',
          content: (
            <UnderConstruction
              title="Structure DAG"
              message={
                <>
                  This page will show a "Structure" DAG of Types and Ops
                  centered at this particular op version.
                </>
              }
            />
          ),
        },
      ]}
    />
  );
  // return ;
};

const OpVersionOpTree: React.FC<{opVersion: WFOpVersion}> = ({opVersion}) => {
  return (
    <ul style={{margin: 0}}>
      {opVersion.invokes().map((v, i) => {
        return (
          <li key={i}>
            <OpVersionLink opName={v.op().name()} version={v.version()} />
            <OpVersionOpTree opVersion={v} />
          </li>
        );
      })}
    </ul>
  );
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
