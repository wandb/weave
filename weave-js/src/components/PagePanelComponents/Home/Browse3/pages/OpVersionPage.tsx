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
  const {entity, project, opId, versionIndex, category} = opVersion;

  const opVersions = useOpVersions(entity, project, {
    opIds: [opId],
  });
  const opVersionCount = (opVersions.result ?? []).length;
  const calls = useCalls(entity, project, {
    opVersionRefs: [uri],
  });
  const opVersionCallCount = (calls.result ?? []).length;

  return (
    <SimplePageLayoutWithHeader
      title={opVersionText(opId, versionIndex)}
      headerContent={
        <SimpleKeyValueTable
          data={{
            Name: (
              <>
                {opId}{' '}
                {(!opVersions.loading || opVersionCount > 0) && (
                  <>
                    [
                    <OpVersionsLink
                      entity={entity}
                      project={project}
                      filter={{
                        opName: opId,
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
            Version: <>{versionIndex}</>,
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
            ...(category
              ? {
                  Category: <CategoryChip value={category} />,
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
              opName={opId}
              opVersions={(opVersions.result ?? []).slice().reverse()} // put in increasing order
              currentVersionURI={uri}
            />
          ),
        },
        {
          label: 'Use',
          content: <TabUseOp name={opNiceName(opId)} uri={uri} />,
        },
      ]}
    />
  );
};
