import React, {useMemo} from 'react';

import {LoadingDots} from '../../../../LoadingDots';
import {NotFoundPanel} from '../NotFoundPanel';
import {OpCodeViewer} from '../OpCodeViewer';
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
import {useWFHooks} from './wfReactInterface/context';
import {opVersionKeyToRefUri} from './wfReactInterface/utilities';
import {OpVersionSchema} from './wfReactInterface/wfDataModelHooksInterface';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  version: string;
}> = props => {
  const {useOpVersion} = useWFHooks();

  const opVersion = useOpVersion({
    entity: props.entity,
    project: props.project,
    opId: props.opName,
    versionHash: props.version,
  });
  if (opVersion.loading) {
    return <CenteredAnimatedLoader />;
  } else if (opVersion.result == null) {
    return <NotFoundPanel title="Op not found" />;
  }
  return <OpVersionPageInner opVersion={opVersion.result} />;
};

const OpVersionPageInner: React.FC<{
  opVersion: OpVersionSchema;
}> = ({opVersion}) => {
  const {useOpVersions, useCallsStats} = useWFHooks();
  const uri = opVersionKeyToRefUri(opVersion);
  const {entity, project, opId, versionIndex} = opVersion;

  const opVersions = useOpVersions(entity, project, {
    opIds: [opId],
  });
  const opVersionCount = (opVersions.result ?? []).length;
  const callsStats = useCallsStats(entity, project, {
    opVersionRefs: [uri],
  });
  const opVersionCallCount = callsStats?.result?.count ?? 0;
  const useOpSupported = useMemo(() => {
    // TODO: We really want to return `True` only when
    // the op is not a bound op. However, we don't have
    // that data available yet.
    return true;
  }, []);

  return (
    <SimplePageLayoutWithHeader
      title={opVersionText(opId, versionIndex)}
      headerContent={
        <SimpleKeyValueTable
          data={{
            Name: (
              <>
                {opId}{' '}
                {opVersions.loading ? (
                  <LoadingDots />
                ) : (
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
              !callsStats.loading || opVersionCallCount > 0 ? (
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
              opVersions={opVersions.result ?? []}
              currentVersionURI={uri}
            />
          ),
        },
        ...(useOpSupported
          ? [
              {
                label: 'Use',
                content: <TabUseOp name={opNiceName(opId)} uri={uri} />,
              },
            ]
          : []),
      ]}
    />
  );
};
