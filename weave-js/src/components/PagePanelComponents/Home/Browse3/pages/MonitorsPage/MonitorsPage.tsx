import {Box} from '@mui/material';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {IconPencilEdit} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {ALL_TRACES_OR_CALLS_REF_KEY} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {EMPTY_PROPS_MONITORS} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/EmptyContent';
import {CreateMonitorDrawer} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/CreateMonitorDrawer';
import {FilterableObjectVersionsTable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/ObjectsPage/ObjectVersionsTable';
import {Query} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientInterface/query';
import {useCallsStats} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRef';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';
import React, {useMemo, useState} from 'react';

import {MONITORED_FILTER_VALUE} from '../../filters/common';

export const MonitorsPage = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => {
  const [isCreateDrawerOpen, setIsCreateDrawerOpen] = useState(false);
  const [selectedMonitor, setSelectedMonitor] = useState<
    ObjectVersionSchema | undefined
  >();
  return (
    <Tailwind>
      <Box>
        <Box className="mx-16 my-16 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Monitors</h1>
          <Button
            icon="add-new"
            variant="ghost"
            tooltip="Create a new monitor"
            onClick={() => {
              setSelectedMonitor(undefined);
              setIsCreateDrawerOpen(true);
            }}>
            Create monitor
          </Button>
        </Box>
        <FilterableObjectVersionsTable
          entity={entity}
          project={project}
          objectTitle="Monitor"
          hideCategoryColumn
          frozenFilter={{
            baseObjectClass: 'Monitor',
          }}
          metadataOnly={false}
          propsEmpty={EMPTY_PROPS_MONITORS}
          keepNestedVal={['query']}
          hidePeerVersionsColumn
          hideVersionSuffix
          actionMenu={obj => (
            <PopupDropdown
              sections={[
                [
                  {
                    key: 'edit',
                    text: 'Edit',
                    icon: <IconPencilEdit style={{marginRight: '8px'}} />,
                    onClick: () => setIsCreateDrawerOpen(true),
                  },
                ],
              ]}
              trigger={<Button icon="overflow-horizontal" variant="ghost" />}
              offset="0px, -20px"
              onOpen={() => setSelectedMonitor(obj)}
            />
          )}
          customColumns={[
            {
              field: 'description',
              headerName: 'Description',
              flex: 1,
              valueGetter: (_, row) => row.obj.val['description'],
              renderCell: params => <CellValue value={params.value} />,
            },
            {
              field: 'samplingRate',
              headerName: 'Sampling rate',
              width: 120,
              valueGetter: (_, row) => row.obj.val['sampling_rate'],
              renderCell: params => (
                <CellValue value={`${params.value * 100}%`} />
              ),
            },
            {
              field: 'ops',
              headerName: 'Ops',
              flex: 1,
              valueGetter: (_, row) => row.obj.val['op_names'],
              renderCell: params => {
                const opRefs: string[] = params.value;
                if (opRefs.length === 0) {
                  return null;
                }
                let firstOpRef: WeaveObjectRef | null = null;
                try {
                  firstOpRef = parseRef(opRefs[0]) as WeaveObjectRef;
                } catch (e) {
                  return <span>Incorrect op ref: {opRefs[0]}</span>;
                }
                return (
                  <div className="flex items-center gap-2">
                    {opRefs[0] !== ALL_TRACES_OR_CALLS_REF_KEY ? (
                      <SmallRef objRef={firstOpRef} />
                    ) : null}
                    {opRefs.length > 1 ? (
                      <span>{`+${opRefs.length - 1}`}</span>
                    ) : null}
                  </div>
                );
              },
            },
            {
              field: 'scorers',
              headerName: 'Scorers',
              flex: 1,
              valueGetter: (_, row) => row.obj.val['scorers'],
              renderCell: params => {
                const scorerRefs: string[] = params.value;
                return scorerRefs.length > 0 ? (
                  <div className="flex items-center gap-2">
                    <CellValue value={scorerRefs[0]} />
                    {scorerRefs.length > 1 ? (
                      <span>{`+${scorerRefs.length - 1}`}</span>
                    ) : null}
                  </div>
                ) : null;
              },
            },
            {
              field: 'active',
              headerName: 'Active',
              valueGetter: (_, row) => {
                return row.obj.val['active'];
              },
              renderCell: params => {
                return <CellValue value={params.value} />;
              },
            },
            {
              field: 'callCount',
              headerName: 'Calls',
              valueGetter: (_, row) => {
                return row.id;
              },
              renderCell: params => (
                <CallCountCell
                  monitorRef={params.value}
                  entity={entity}
                  project={project}
                />
              ),
            },
          ]}
        />
      </Box>
      <CreateMonitorDrawer
        entity={entity}
        project={project}
        open={isCreateDrawerOpen}
        onClose={() => setIsCreateDrawerOpen(false)}
        monitor={selectedMonitor}
      />
    </Tailwind>
  );
};

const CallCountCell = ({
  monitorRef,
  entity,
  project,
}: {
  monitorRef: string;
  entity: string;
  project: string;
}) => {
  const query: Query = useMemo(() => {
    return {
      $expr: {
        $contains: {
          input: {$getField: MONITORED_FILTER_VALUE},
          substr: {
            $literal: `${monitorRef.split(':').slice(0, -1).join(':')}:`,
          },
        },
      },
    };
  }, [monitorRef]);
  const callsStats = useCallsStats({
    entity,
    project,
    filter: {},
    query,
  });
  if (callsStats.loading) {
    return <LoadingDots />;
  }
  return (
    <CellValue
      value={`${callsStats.result?.count} ${maybePluralizeWord(
        callsStats.result?.count || 0,
        'call'
      )}`}
    />
  );
};
