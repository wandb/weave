import React from 'react';

import {OpCodeViewer} from '../OpCodeViewer';
import {CategoryChip} from './common/CategoryChip';
import {
  CallsLink,
  opNiceName,
  OpVersionsLink,
  opVersionText,
} from './common/Links';
import {CenteredAnimatedLoader} from './common/Loader';
import {
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {TabUseOp} from './TabUseOp';
import {
  opVersionKeyToRefUri,
  OpVersionSchema,
  useCalls,
  useOpVersion,
  useOpVersions,
} from './wfReactInterface/interface';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  version: string;
}> = props => {
  const opVersion = useOpVersion({
    entity: props.entity,
    project: props.project,
    opId: props.opName,
    versionHash: props.version,
  });
  if (opVersion.loading) {
    return <CenteredAnimatedLoader />;
  } else if (opVersion.result == null) {
    return <div>Op version not found</div>;
  }
  return <OpVersionPageInner opVersion={opVersion.result} />;
};

const OpVersionPageInner: React.FC<{
  opVersion: OpVersionSchema;
}> = ({opVersion}) => {
  const uri = opVersionKeyToRefUri(opVersion);
  const entity = opVersion.entity;
  const project = opVersion.project;
  const opName = opVersion.opId;
  const opVersions = useOpVersions(entity, project, {
    opIds: [opName],
  });
  const opVersionCount = (opVersions.result ?? []).length;
  const calls = useCalls(entity, project, {
    opVersionRefs: [uri],
  });
  const opVersionCallCount = (calls.result ?? []).length;
  const opVersionIndex = opVersion.versionIndex;
  const opVersionCategory = opVersion.category;

  return (
    <SimplePageLayoutWithHeader
      title={opVersionText(opName, opVersionIndex)}
      headerContent={
        <SimpleKeyValueTable
          data={{
            Name: (
              <>
                {opName}{' '}
                {(!opVersions.loading || opVersionCount > 0) && (
                  <>
                    [
                    <OpVersionsLink
                      entity={entity}
                      project={project}
                      filter={{
                        opName,
                      }}
                      versionCount={opVersionCount}
                      neverPeek
                      variant="secondary"
                    />
                    ]
                  </>
                )}
              </>
            ),
            Version: <>{opVersionIndex}</>,
            Calls:
              !calls.loading || opVersionCallCount > 0 ? (
                <CallsLink
                  entity={entity}
                  project={project}
                  callCount={opVersionCallCount}
                  filter={{
                    opVersionRefs: [uri],
                  }}
                  neverPeek
                  variant="secondary"
                />
              ) : (
                <></>
              ),
            ...(opVersionCategory
              ? {
                  Category: <CategoryChip value={opVersionCategory} />,
                }
              : {}),
          }}
        />
      }
      tabs={[
        {
          label: 'Code',
          content: (
            <OpCodeViewer
              entity={entity}
              project={project}
              opName={opName}
              opVersions={opVersions.result ?? []} // put in increasing order
              currentVersionURI={uri}
            />
          ),
        },
        {
          label: 'Use',
          content: <TabUseOp name={opNiceName(opName)} uri={uri} />,
        },
        {
          label: 'Execute',
          content: (
            <UnderConstruction
              title="Execute"
              message={
                <>
                  This page will allow you to call this op version with specific
                  inputs.
                </>
              }
            />
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
};
