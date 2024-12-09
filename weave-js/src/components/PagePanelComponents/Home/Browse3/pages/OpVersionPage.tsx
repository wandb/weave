import React, {useMemo} from 'react';

import {Icon} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
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
  ScrollableTabContent,
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

  const opVersions = useOpVersions(
    entity,
    project,
    {
      opIds: [opId],
    },
    undefined, // limit
    true // metadataOnly
  );
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
        <Tailwind>
          <div className="grid w-full auto-cols-max grid-flow-col gap-[16px] text-[14px]">
            <div className="block">
              <p className="text-moon-500">Name</p>
              <div className="flex items-center">
                <OpVersionsLink
                  entity={entity}
                  project={project}
                  filter={{
                    opName: opId,
                  }}
                  versionCount={opVersionCount}
                  neverPeek
                  variant="secondary">
                  <div className="group flex items-center font-semibold">
                    <span>{opId}</span>
                    {opVersions.loading ? (
                      <LoadingDots />
                    ) : (
                      <span className="ml-[4px]">
                        ({opVersionCount} version
                        {opVersionCount !== 1 ? 's' : ''})
                      </span>
                    )}
                    <Icon
                      name="forward-next"
                      width={16}
                      height={16}
                      className="ml-[2px] opacity-0 group-hover:opacity-100"
                    />
                  </div>
                </OpVersionsLink>
              </div>
            </div>
            <div className="block">
              <p className="text-moon-500">Version</p>
              <p>{versionIndex}</p>
            </div>
            <div className="block">
              <p className="text-moon-500">Calls:</p>
              {!callsStats.loading || opVersionCallCount > 0 ? (
                <div className="group flex w-max items-center">
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
                  <Icon
                    name="forward-next"
                    width={16}
                    height={16}
                    className="ml-[2px] text-teal-500 opacity-0 hover:hidden group-hover:opacity-100"
                  />
                </div>
              ) : (
                <p>-</p>
              )}
            </div>
          </div>
        </Tailwind>
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
                content: (
                  <ScrollableTabContent>
                    <Tailwind>
                      <TabUseOp name={opNiceName(opId)} uri={uri} />
                    </Tailwind>
                  </ScrollableTabContent>
                ),
              },
            ]
          : []),
      ]}
    />
  );
};
