import {Box, TextField, Typography} from '@material-ui/core';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {useMemo} from 'react';
import {Button} from 'semantic-ui-react';

import {Browse2OpDefCode} from '../../Browse2/Browse2OpDefCode';
import {StreamId} from '../../Browse2/callTree';
import {useFirstCall, useOpSignature} from '../../Browse2/callTreeHooks';
import {Paper} from '../../Browse2/CommonLib';
import {CallsTable} from './CallsPage';
import {OpLink, OpVersionLink, TypeVersionLink} from './common/Links';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {FilterableOpVersionsTable} from './OpVersionsPage';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFOpVersion} from './wfInterface/types';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  version: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const opVersion = orm.projectConnection.opVersion(
    props.opName,
    props.version
  );
  if (opVersion == null) {
    return <>Op Version not found</>;
  }
  return <OpVersionPageInner opVersion={opVersion} />;
};

const OpVersionPageInner: React.FC<{
  opVersion: WFOpVersion;
}> = ({opVersion}) => {
  const uri = opVersion.refUri();
  const entity = opVersion.entity();
  const project = opVersion.project();
  const opName = opVersion.op().name();
  const opVersionHash = opVersion.version();

  const streamId = useMemo(
    () => ({
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    }),
    [entity, project]
  );

  return (
    <SimplePageLayout
      title={opName + ' : ' + opVersionHash}
      tabs={[
        {
          label: 'Overview',
          content: (
            <ScrollableTabContent>
              <SimpleKeyValueTable
                data={{
                  Name: (
                    <OpLink
                      entityName={opVersion.entity()}
                      projectName={opVersion.project()}
                      opName={opName}
                    />
                  ),
                  Category: (
                    <OpVersionCategoryChip
                      opCategory={opVersion.opCategory()}
                    />
                  ),
                  Version: opVersionHash,
                  'Input Types': (
                    <ul style={{margin: 0}}>
                      {opVersion.inputTypesVersions().map((t, i) => (
                        <li key={i}>
                          <TypeVersionLink
                            entityName={t.entity()}
                            projectName={t.project()}
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
                            entityName={t.entity()}
                            projectName={t.project()}
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
              entity={entity}
              project={project}
              frozenFilter={{
                opVersions: [opName + ':' + opVersionHash],
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
            <OpVersionLink
              entityName={v.entity()}
              projectName={v.project()}
              opName={v.op().name()}
              version={v.version()}
            />
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
