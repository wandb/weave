import {Box, Typography} from '@mui/material';
import {GridFilterItem} from '@mui/x-data-grid-pro';
import {ButtonVariants} from '@wandb/weave/components/Button';
import {TrackedButton} from '@wandb/weave/components/Button/TrackedButton';
import {IconNames} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {BooleanIcon} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValueBoolean';
import {
  useEntityProject,
  useWeaveflowRouteContext,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {MONITORED_FILTER_VALUE} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/filters/common';
import {FilterTagItem} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/filters/FilterTagItem';
import {NotFoundPanel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/NotFoundPanel';
import {CallsTable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/CallsTable';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/SimplePageLayout';
import {SafeOpRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/MonitorsPage';
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
import {SmallRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRef';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import {useObjectViewEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import {parseRef} from '@wandb/weave/react';
import React, {useCallback, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {MonitorDrawerRouter} from './MonitorFormDrawer';

const MONITOR_VERSIONS_SORT_KEY: SortBy[] = [
  {field: 'created_at', direction: 'desc'},
];
const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const MonitorPage = (props: {
  objectName: string;
  version: string;
  objectVersion: ObjectVersionSchema;
}) => {
  useObjectViewEvent(props.objectVersion);

  const {entity, project} = useEntityProject();

  const monitorVersionFilter = useMemo(
    () => ({
      objectIds: [props.objectName],
    }),
    [props.objectName]
  );

  const objectVersionResults = useRootObjectVersions({
    entity,
    project,
    filter: monitorVersionFilter,
    sortBy: MONITOR_VERSIONS_SORT_KEY,
  });

  const monitorVersions = objectVersionResults.result || [];
  const isLoading = objectVersionResults.loading;

  if (isLoading) {
    return (
      <Tailwind>
        <div className="flex min-h-[100vh] items-center justify-center">
          <LoadingDots />
        </div>
      </Tailwind>
    );
  }

  return monitorVersions === null || monitorVersions.length === 0 ? (
    <NotFoundPanel title="Monitor not found" />
  ) : (
    <MonitorPageInner monitorVersions={monitorVersions} />
  );
};

const MonitorPageInner = ({
  monitorVersions,
}: {
  monitorVersions: ObjectVersionSchema[];
}) => {
  const {entity, project} = useEntityProject();

  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const allVersionsSchema = useMemo(
    () => ({...monitorVersions[0], versionHash: '*'}),
    [monitorVersions]
  );

  const allVersionsRef = useMemo(
    () => objectVersionKeyToRefUri(allVersionsSchema),
    [allVersionsSchema]
  );

  const callsFilterModel = useMemo(
    () => ({
      items: [
        {
          field: MONITORED_FILTER_VALUE,
          operator: '(monitored): by',
          value: allVersionsRef,
        },
      ],
    }),
    [allVersionsRef]
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

  const callCountQuery: Query = useMemo(
    () => matchAllMonitorVersionsQuery(allVersionsRef),
    [allVersionsRef]
  );

  const {result: callCountResult} = useCallsStats({
    entity,
    project,
    filter: {},
    query: callCountQuery,
  });

  const handleEditClick = useCallback(() => setIsDrawerOpen(true), []);
  const handleCloseDrawer = useCallback(() => setIsDrawerOpen(false), []);

  return (
    <>
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
              <div className="ml-auto flex-shrink-0">
                <TrackedButton
                  title="Edit monitor"
                  tooltip="Edit monitor"
                  variant="ghost"
                  size="medium"
                  icon="pencil-edit"
                  onClick={handleEditClick}
                  trackedName="edit-monitor">
                  Edit monitor
                </TrackedButton>
                <DeleteObjectButtonWithModal
                  overrideDisplayStr={monitorVersions[0].val['name']}
                  objVersionSchema={allVersionsSchema}
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
                          {!monitorVersions[0].val['op_names'] ||
                          monitorVersions[0].val['op_names'].length === 0 ? (
                            <span>All ops</span>
                          ) : (
                            monitorVersions[0].val['op_names'].map(
                              (opRefUri: string) => (
                                <SafeOpRef key={opRefUri} opRef={opRefUri} />
                              )
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
                    <TrackedButton
                      variant={ButtonVariants.Secondary}
                      icon={IconNames.Table}
                      onClick={onGoToTableClick}
                      trackedName="go-to-table-from-monitor">
                      Go to table
                    </TrackedButton>
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
      <MonitorDrawerRouter
        open={isDrawerOpen}
        onClose={handleCloseDrawer}
        monitor={monitorVersions[0]}
      />
    </>
  );
};

export function matchAllMonitorVersionsQuery(monitorRef: string): Query {
  return {
    $expr: {
      $contains: {
        input: {$getField: MONITORED_FILTER_VALUE},
        substr: {$literal: `${monitorRef.split(':').slice(0, -1).join(':')}:`},
      },
    },
  };
}
