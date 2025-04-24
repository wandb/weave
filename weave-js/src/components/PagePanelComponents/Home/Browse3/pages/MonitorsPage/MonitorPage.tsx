import {Box, Typography} from '@mui/material';
import {GridFilterItem} from '@mui/x-data-grid-pro';
import {IconNames} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {UserLink} from '@wandb/weave/components/UserLink';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {Button, ButtonVariants} from '../../../../../Button';
import {BooleanIcon} from '../../../Browse2/CellValueBoolean';
import {useWeaveflowRouteContext} from '../../context';
import {FilterTagItem} from '../../filters/FilterTagItem';
import {NotFoundPanel} from '../../NotFoundPanel';
import {SmallOpVersionsRef} from '../../smallRef/SmallOpVersionsRef';
import {SmallRef} from '../../smallRef/SmallRef';
import {CallsTable} from '../CallsPage/CallsTable';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from '../common/SimplePageLayout';
import {DeleteObjectButtonWithModal} from '../ObjectsPage/ObjectDeleteButtons';
import {ObjectIcon} from '../ObjectsPage/ObjectVersionPage';
import {useWFHooks} from '../wfReactInterface/context';
import {Query} from '../wfReactInterface/traceServerClientInterface/query';
import {SortBy} from '../wfReactInterface/traceServerClientTypes';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {queryToGridFilterModel} from './saveViewUtil';

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
  const {useRootObjectVersions} = useWFHooks();

  const monitorVersionFilter = useMemo(
    () => ({
      objectIds: [props.objectName],
    }),
    [props.objectName]
  );

  const objectVersionResults = useRootObjectVersions(
    props.entity,
    props.project,
    monitorVersionFilter,
    undefined,
    undefined,
    undefined,
    MONITOR_VERSIONS_SORT_KEY
  );

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
          field: 'feedback.[*].trigger_ref',
          operator: '(string): in',
          value: allVersionRefs,
        },
      ],
    }),
    [allVersionRefs]
  );
  console.log(monitorVersions[0]);
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

  const {useCallsStats} = useWFHooks();

  const callCountQuery: Query = useMemo(() => {
    const allVersionRefOperands = allVersionRefs.map(versionRefUri => ({
      $literal: versionRefUri,
    }));
    return {
      $expr: {
        $in: [{$getField: 'feedback.[*].trigger_ref'}, allVersionRefOperands],
      },
    };
  }, [allVersionRefs]);

  const {result: callCountResult} = useCallsStats(
    entity,
    project,
    {},
    callCountQuery
  );

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
