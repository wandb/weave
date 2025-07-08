import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {TrackedButton} from '@wandb/weave/components/Button/TrackedButton';
import {IconPencilEdit} from '@wandb/weave/components/Icon';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {CellValue} from '@wandb/weave/components/PagePanelComponents/Home/Browse2/CellValue';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {ALL_TRACES_OR_CALLS_REF_KEY} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {EMPTY_PROPS_MONITORS} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/EmptyContent';
import {SimplePageLayout} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/SimplePageLayout';
import {MonitorDrawerRouter} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/MonitorFormDrawer';
import {matchAllMonitorVersionsQuery} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/MonitorPage';
import {FilterableObjectVersionsTable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/ObjectsPage/ObjectVersionsTable';
import {Query} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/traceServerClientInterface/query';
import {useCallsStats} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRef} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/smallRef/SmallRef';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {maybePluralizeWord} from '@wandb/weave/core/util/string';
import {parseRefMaybe} from '@wandb/weave/react';
import React, {useMemo, useState} from 'react';

export const MonitorsPage = () => {
  const {entity, project} = useEntityProject();

  const [isCreateDrawerOpen, setIsCreateDrawerOpen] = useState(false);

  const [selectedMonitor, setSelectedMonitor] = useState<
    ObjectVersionSchema | undefined
  >();

  const handleCreateMonitor = () => {
    setSelectedMonitor(undefined);
    setIsCreateDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsCreateDrawerOpen(false);
  };

  return (
    <>
      <SimplePageLayout
        title="Monitors"
        hideTabsIfSingle
        headerExtra={
          <MonitorsPageHeaderExtra onCreateMonitor={handleCreateMonitor} />
        }
        tabs={[
          {
            label: '',
            content: (
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
                    trigger={
                      <TrackedButton
                        icon="overflow-horizontal"
                        variant="ghost"
                        trackedName="monitor-overflow-menu-edit"
                      />
                    }
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
                      if (!opRefs || opRefs.length === 0) {
                        return <span>All ops</span>;
                      }
                      return (
                        <div className="flex items-center gap-2">
                          {opRefs[0] !== ALL_TRACES_OR_CALLS_REF_KEY ? (
                            <SafeOpRef opRef={opRefs[0]} />
                          ) : null}
                          {opRefs[0] === ALL_TRACES_OR_CALLS_REF_KEY ? (
                            <span>All calls</span>
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
            ),
          },
        ]}
      />

      <MonitorDrawerRouter
        open={isCreateDrawerOpen}
        onClose={handleCloseDrawer}
        monitor={selectedMonitor}
      />
    </>
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
  const query: Query = useMemo(
    () => matchAllMonitorVersionsQuery(monitorRef),
    [monitorRef]
  );
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

const MonitorsPageHeaderExtra: React.FC<{
  onCreateMonitor: () => void;
}> = ({onCreateMonitor}) => {
  return (
    <Tailwind>
      <div className="mr-16 flex gap-8">
        <TrackedButton
          icon="add-new"
          variant="ghost"
          onClick={onCreateMonitor}
          trackedName="new-monitor"
          tooltip="Create a new monitor">
          New monitor
        </TrackedButton>
      </div>
    </Tailwind>
  );
};

export const SafeOpRef = ({opRef}: {opRef: string}) => {
  const ref = parseRefMaybe(opRef);
  return ref ? (
    <SmallRef objRef={ref} />
  ) : (
    <span>Incorrect op ref: {opRef}</span>
  );
};
