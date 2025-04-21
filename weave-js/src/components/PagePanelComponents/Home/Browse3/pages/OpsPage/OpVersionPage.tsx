import {Button} from '@wandb/weave/components/Button';
import {UserLink} from '@wandb/weave/components/UserLink';
import React, {useContext, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {Icon} from '../../../../../Icon';
import {LoadingDots} from '../../../../../LoadingDots';
import {Tailwind} from '../../../../../Tailwind';
import {Timestamp} from '../../../../../Timestamp';
import {
  useClosePeek,
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {NotFoundPanel} from '../../NotFoundPanel';
import {OpCodeViewer} from '../../OpCodeViewer';
import {DeleteModal, useShowDeleteButton} from '../common/DeleteModal';
import {CallsLink, OpVersionsLink, opVersionText} from '../common/Links';
import {CenteredAnimatedLoader} from '../common/Loader';
import {opNiceName} from '../common/opNiceName';
import {
  ScrollableTabContent,
  SimplePageLayoutWithHeader,
} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {OpVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {TabUseOp} from './Tabs/TabUseOp';

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
  const {entity, project, opId, versionIndex, createdAtMs} = opVersion;

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
  const showDeleteButton = useShowDeleteButton(entity);

  return (
    <SimplePageLayoutWithHeader
      title={opVersionText(opId, versionIndex)}
      headerContent={
        <Tailwind>
          <div className="grid w-full grid-flow-col grid-cols-[auto_auto_auto_1fr] gap-[16px] text-[14px]">
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
              <p className="text-moon-500">Last updated</p>
              <p>
                <Timestamp value={createdAtMs / 1000} format="relative" />
              </p>
            </div>
            {opVersion.userId && (
              <div className="block">
                <p className="text-moon-500">Last updated by</p>
                <UserLink userId={opVersion.userId} includeName />
              </div>
            )}
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
            {showDeleteButton && (
              <div className="ml-auto">
                <DeleteOpButtonWithModal opVersionSchema={opVersion} />
              </div>
            )}
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

const DeleteOpButtonWithModal: React.FC<{
  opVersionSchema: OpVersionSchema;
  overrideDisplayStr?: string;
}> = ({opVersionSchema, overrideDisplayStr}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const closePeek = useClosePeek();
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const routerContext = useWeaveflowCurrentRouteContext();
  const history = useHistory();
  const {opVersionsDelete} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const deleteStr =
    overrideDisplayStr ??
    `${opVersionSchema.opId}:v${opVersionSchema.versionIndex}`;

  const onSuccess = () => {
    if (isPeeking) {
      closePeek();
    } else {
      history.push(
        routerContext.opVersionsUIUrl(
          opVersionSchema.entity,
          opVersionSchema.project,
          {
            opName: opVersionSchema.opId,
          }
        )
      );
    }
  };

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
        tooltip="Delete this Op version"
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTitleStr={deleteStr}
        onDelete={() =>
          opVersionsDelete(
            opVersionSchema.entity,
            opVersionSchema.project,
            opVersionSchema.opId,
            [opVersionSchema.versionHash]
          )
        }
        onSuccess={onSuccess}
      />
    </>
  );
};
