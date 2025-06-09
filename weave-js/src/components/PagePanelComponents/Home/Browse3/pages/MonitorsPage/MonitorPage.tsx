import {Box, Typography} from '@mui/material';
import {GridFilterItem} from '@mui/x-data-grid-pro';
import {Button, ButtonVariants} from '@wandb/weave/components/Button';
import {IconNames} from '@wandb/weave/components/Icon';
import {BooleanIcon} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValueBoolean';
import {useWeaveflowRouteContext} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {FilterTagItem} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/filters/FilterTagItem';
import {NotFoundPanel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotFoundPanel';
import {CallsTable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/CallsTable';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/SimplePageLayout';
import {DeleteObjectButtonWithModal} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/ObjectsPage/ObjectDeleteButtons';
import {ObjectIcon} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/ObjectsPage/ObjectVersionPage';
import {queryToGridFilterModel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/SavedViews/savedViewUtil';
import {Query} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientInterface/query';
import {SortBy} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientTypes';
import {
  useCallsStats,
  useRootObjectVersions,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/utilities';
import {ObjectVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallOpVersionsRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallOpVersionsRef';
import {SmallRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRef';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {MONITORED_FILTER_VALUE} from '../../filters/common';

const MONITOR_VERSIONS_SORT_KEY: SortBy[] = [
  {field: 'created_at', direction: 'desc'},
];
const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const MonitorPage = (props: {
  entity: string;
  project: string;
  objectName: string;
  version: string;
}) => {
  const monitorVersionFilter = useMemo(
    () => ({
      objectIds: [props.objectName],
    }),
    [props.objectName]
  );

  const objectVersionResults = useRootObjectVersions({
    entity: props.entity,
    project: props.project,
    filter: monitorVersionFilter,
    sortBy: MONITOR_VERSIONS_SORT_KEY,
  });

  const monitorVersions = objectVersionResults.result || [];
  return monitorVersions === null || monitorVersions.length === 0 ? (
    <NotFoundPanel title="Monitor not found" />
  ) : (
    <MonitorPageInner
      entity={props.entity}
      project={props.project}
      monitorVersions={monitorVersions}
    />
  );
};

const MonitorPageInner = ({
  entity,
  project,
  monitorVersions,
}: {
  entity: string;
  project: string;
  monitorVersions: ObjectVersionSchema[];
}) => {
  const allVersionRefs = useMemo(() => {
    return monitorVersions.map(v => objectVersionKeyToRefUri(v));
  }, [monitorVersions]);

  const callsFilterModel = useMemo(
    () => ({
      items: [
        {
          field: MONITORED_FILTER_VALUE,
          operator: '(string): in',
          value: allVersionRefs,
        },
      ],
    }),
    [allVersionRefs]
  );

  const filterItems: GridFilterItem[] = useMemo(
    () => queryToGridFilterModel(monitorVersions[0].val['query'])?.items || [],
    [monitorVersions]
  );

  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  const onGoToTableClick = useCallback(() => {
    const url = baseRouter.callsUIUrl(
      entity,
      project,
      undefined,
      callsFilterModel
    );
    history.push(url);
  }, [baseRouter, history, callsFilterModel, entity, project]);

  const callCountQuery: Query = useMemo(() => {
    const allVersionRefOperands = allVersionRefs.map(versionRefUri => ({
      $literal: versionRefUri,
    }));
    return {
      $expr: {
        $in: [{$getField: MONITORED_FILTER_VALUE}, allVersionRefOperands],
      },
    };
  }, [allVersionRefs]);

  const {result: callCountResult} = useCallsStats({
    entity,
    project,
    filter: {},
    query: callCountQuery,
  });

  return (
    <SimplePageLayoutWithHeader
      title={
        <Tailwind>
          <div className="flex items-center gap-8">
            <ObjectIcon baseObjectClass="Monitor" />
            {monitorVersions[0].val['name']}
          </div>
        </Tailwind>
      }
      headerContent={
        <Tailwind>
          <div className="grid-cols-auto grid w-full grid-flow-col gap-16 text-sm">
            <div className="block">
              <p className="text-moon-500">Name</p>
              <p>{monitorVersions[0].val['name']}</p>
            </div>
            <div className="block">
              <p className="text-moon-500">Last updated</p>
              <p>
                <Timestamp
                  value={monitorVersions[0].createdAtMs / 1000}
                  format="relative"
                />
              </p>
            </div>
            {monitorVersions[0].userId && (
              <div className="block">
                <p className="text-moon-500">Last updated by</p>
                <UserLink userId={monitorVersions[0].userId} includeName />
              </div>
            )}
            <div className="ml-auto">
              <DeleteObjectButtonWithModal
                objVersionSchema={monitorVersions[0]}
              />
            </div>
          </div>
        </Tailwind>
      }
      tabs={[
        {
          label: 'Monitor',
          content: (
            <ScrollableTabContent>
              <Tailwind>
                <Box className="flex-0-auto mb-8 h-full">
                  <Typography
                    variant="h6"
                    sx={{...typographyStyle}}
                    className="font-semibold">
                    Monitor details
                  </Typography>
                </Box>
                <SimpleKeyValueTable
                  data={{
                    Description: monitorVersions[0].val['description'],
                    Active: (
                      <BooleanIcon value={monitorVersions[0].val['active']} />
                    ),
                    'Monitored Ops': (
                      <Box className="flex gap-2">
                        {monitorVersions[0].val['op_names'].map(
                          (opRefUri: string) => (
                            <SmallOpVersionsRef
                              key={opRefUri}
                              objRef={parseRef(opRefUri) as WeaveObjectRef}
                            />
                          )
                        )}
                      </Box>
                    ),
                    'Additional filters': (
                      <Box className="flex gap-2">
                        {filterItems.map(item => (
                          <FilterTagItem
                            key={item.id}
                            entity={entity}
                            project={project}
                            item={item}
                            disableRemove
                          />
                        ))}
                      </Box>
                    ),
                    'Sampling rate': `${
                      monitorVersions[0].val['sampling_rate'] * 100
                    }%`,
                    Scorers: (
                      <Box className="flex gap-2">
                        {monitorVersions[0].val['scorers'].map(
                          (scorerRefUri: string) => (
                            <SmallRef
                              objRef={parseRef(scorerRefUri)}
                              key={scorerRefUri}
                            />
                          )
                        )}
                      </Box>
                    ),
                  }}
                />
              </Tailwind>
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Calls',
          content: (
            <Tailwind>
              <Box className="flex flex-col gap-16 p-16">
                <Box className="flex justify-between">
                  <span>
                    {callCountResult && (
                      <>
                        {callCountResult.count}{' '}
                        {maybePluralizeWord(callCountResult.count, 'call')}
                      </>
                    )}
                  </span>
                  <Button
                    variant={ButtonVariants.Secondary}
                    icon={IconNames.Table}
                    onClick={onGoToTableClick}>
                    Go to table
                  </Button>
                </Box>
                <CallsTable
                  hideControls
                  paginationModel={{page: 0, pageSize: 10}}
                  entity={entity}
                  project={project}
                  filterModel={callsFilterModel}
                />
              </Box>
            </Tailwind>
          ),
        },
      ]}
    />
  );
};
