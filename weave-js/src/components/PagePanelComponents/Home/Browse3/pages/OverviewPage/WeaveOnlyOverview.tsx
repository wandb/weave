import {ApolloProvider} from '@apollo/client';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {MOON_100, TEAL_600} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  projectIdFromParts,
  useProjectStats,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {UserLink, useUsers} from '@wandb/weave/components/UserLink';
import {convertBytes} from '@wandb/weave/util';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';
import {Layouts, Responsive as ResponsiveGridLayout} from 'react-grid-layout';
import {Link} from 'react-router-dom';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

import {useLocalStorage} from '../../../../../../util/useLocalStorage';
import {CallsCharts} from '../../charts/CallsCharts';
import {Chart} from '../../charts/Chart';
import {chartAxisFields} from '../../charts/extractData';
import {ExtractedCallData} from '../../charts/types';
import {ChartConfig} from '../../charts/types';
import {useChartsData} from '../../charts/useChartsData';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';
import {DEFAULT_FILTER_CALLS} from '../CallsPage/callsTableQuery';
import {ResizableDrawer} from '../common/ResizableDrawer';

export enum AccessOption {
  Restricted = 'RESTRICTED',
  Private = 'PRIVATE',
  Public = 'USER_READ',
  Open = 'USER_WRITE',
}

type WidgetConfig = {
  id: string;
  type: 'projectInfo' | 'owner' | 'stats' | 'chart' | 'userTraceCountsChart';
  x: number;
  y: number;
  w: number;
  h: number;
  minH?: number;
  maxH?: number;
  minW?: number;
  maxW?: number;
  isResizable?: boolean;
  chartConfig?: ChartConfig;
};

type Project = {
  entityName: string;
  name: string;
  entity: {
    isTeam: boolean;
  };
  user: {
    username: string;
    name: string;
    photoUrl: string | null;
  };
};

export const WeaveOnlyOverviewInner: React.FC<{
  project: Project;
  projectAccess: AccessOption;
}> = ({project, projectAccess}) => {
  const {entityName, projectName} = useMemo(
    () => ({entityName: project.entityName, projectName: project.name}),
    [project]
  );

  const [showChartsDrawer, setShowChartsDrawer] = useState(false);

  const {data: callData, isLoading} = useChartsData({
    entity: entityName,
    project: projectName,
    filter: {} as WFHighLevelCallFilter,
    filterModelProp: DEFAULT_FILTER_CALLS,
    pageSize: 250,
    sortModel: [],
  });

  // Group and count by user
  const userTraceCounts = useMemo(() => {
    if (!callData) return {};
    const filtered = callData.filter(call => call.wb_user_id != null);
    return _.mapValues(_.groupBy(filtered, 'wb_user_id'), arr => arr.length);
  }, [callData]);

  // Prepare data for the Chart widget (must match ExtractedCallData[] type)
  const userTraceCountsData = useMemo(
    () =>
      Object.entries(userTraceCounts).map(([user, count]) => ({
        callId: user, // Use user as unique id
        traceId: '',
        started_at: '',
        wb_user_id: user,
        user, // for xAxis
        count, // for yAxis
      })),
    [userTraceCounts]
  );

  const userInfo = useUsers(Object.keys(userTraceCounts));

  // Local storage key for layout
  const layoutKey = `weave-overview-layout-${project.name}`;
  const defaultLayouts: Layouts = {
    lg: [
      {i: 'projectInfo', x: 0, y: 0, w: 6, h: 2},
      ...(project.user !== null ? [{i: 'owner', x: 6, y: 0, w: 6, h: 2}] : []),
      {i: 'stats', x: 0, y: 2, w: 12, h: 4},
    ],
    md: [
      {i: 'projectInfo', x: 0, y: 0, w: 5, h: 2},
      ...(project.user !== null ? [{i: 'owner', x: 5, y: 0, w: 5, h: 2}] : []),
      {i: 'stats', x: 0, y: 2, w: 10, h: 4},
    ],
    sm: [
      {i: 'projectInfo', x: 0, y: 0, w: 3, h: 2},
      ...(project.user !== null ? [{i: 'owner', x: 3, y: 0, w: 3, h: 2}] : []),
      {i: 'stats', x: 0, y: 2, w: 6, h: 4},
    ],
    xs: [
      {i: 'projectInfo', x: 0, y: 0, w: 2, h: 2},
      ...(project.user !== null ? [{i: 'owner', x: 0, y: 2, w: 2, h: 2}] : []),
      {i: 'stats', x: 0, y: 4, w: 2, h: 4},
    ],
    xxs: [
      {i: 'projectInfo', x: 0, y: 0, w: 2, h: 2},
      ...(project.user !== null ? [{i: 'owner', x: 0, y: 2, w: 2, h: 2}] : []),
      {i: 'stats', x: 0, y: 4, w: 2, h: 4},
    ],
  };
  const [layouts, setLayouts] = useLocalStorage<Layouts>(
    layoutKey,
    defaultLayouts
  );

  const setAllLayouts = (allLayouts: Layouts) => {
    setLayouts({
      lg: allLayouts.lg,
      md: allLayouts.lg,
      sm: allLayouts.lg,
      xs: allLayouts.lg,
      xxs: allLayouts.lg,
    });
  };

  const defaultWidgetConfigs: WidgetConfig[] = [
    {
      id: 'projectInfo',
      type: 'projectInfo' as const,
      x: 0,
      y: 0,
      w: 6,
      h: 2,
    },
    ...(project.user !== null
      ? [
          {
            id: 'owner',
            type: 'owner' as const,
            x: 6,
            y: 0,
            w: 6,
            h: 2,
          },
        ]
      : []),
    {
      id: 'stats',
      type: 'stats' as const,
      x: 0,
      y: 2,
      w: 12,
      h: 4,
    },
  ];

  const [widgetConfigs, setWidgetConfigs] = useLocalStorage<WidgetConfig[]>(
    `${layoutKey}-widgetConfigs`,
    defaultWidgetConfigs
  );

  // Now safe to use widgetConfigs below
  const hasUserTraceCountsChart = widgetConfigs.some(
    w => w.type === 'userTraceCountsChart'
  );
  const addUserTraceCountsChartWidget = () => {
    if (hasUserTraceCountsChart) return;
    const newConfig: WidgetConfig = {
      id: 'userTraceCountsChart',
      type: 'userTraceCountsChart',
      x: 0,
      y: 6,
      w: 12,
      h: 9,
      minH: 9,
      maxH: 9,
      minW: 4,
      maxW: 32,
      isResizable: true,
    };
    setAllLayouts((prevLayouts: Layouts) => ({
      ...prevLayouts,
      lg: [
        ...prevLayouts.lg,
        {
          i: newConfig.id,
          x: newConfig.x,
          y: newConfig.y,
          w: newConfig.w,
          h: newConfig.h,
        },
      ],
    }));
    setWidgetConfigs([...widgetConfigs, newConfig]);
  };

  // Track window width for ResponsiveGridLayout
  const [windowWidth, setWindowWidth] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth - 32 - 60 - 32 : 1024
  );
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const onLayoutChange = (newLayout: any, allLayouts: Layouts) => {
    // Update widgetConfigs with new x, y, w, h from newLayout
    const updatedConfigs = widgetConfigs.map(config => {
      const layoutItem = newLayout.find((l: any) => l.i === config.id);
      if (layoutItem) {
        return {
          ...config,
          x: layoutItem.x,
          y: layoutItem.y,
          w: layoutItem.w,
          h: layoutItem.h,
        };
      }
      return config;
    });
    setWidgetConfigs(updatedConfigs);
    setAllLayouts({...allLayouts, lg: newLayout});
  };

  return (
    <Tailwind className="h-full min-h-screen w-full">
      <div className="mx-32 my-8">
        <button
          className="absolute right-8 top-8 z-20 rounded border border-moon-300 bg-white px-4 py-2 text-xs text-moon-400 hover:bg-moon-200"
          onClick={() => setShowChartsDrawer(true)}>
          Open Call Charts
        </button>
        {!hasUserTraceCountsChart && (
          <button
            className="absolute right-44 top-8 z-20 rounded border border-moon-300 bg-white px-4 py-2 text-xs text-moon-400 hover:bg-moon-200"
            onClick={addUserTraceCountsChartWidget}>
            Add User Trace Counts Chart
          </button>
        )}
        <ResizableDrawer
          open={showChartsDrawer}
          onClose={() => setShowChartsDrawer(false)}
          title="Call Charts">
          <CallsCharts
            entity={project.entityName}
            project={project.name}
            filter={{} as WFHighLevelCallFilter}
            filterModelProp={DEFAULT_FILTER_CALLS}
            addChart={chart => {
              const newConfig: WidgetConfig = {
                id: chart.id,
                type: 'chart',
                x: 0,
                y: 0,
                w: 12,
                h: 9,
                minH: 9,
                maxH: 9,
                minW: 4,
                maxW: 32,
                isResizable: true,
                chartConfig: chart as ChartConfig,
              };
              setAllLayouts((prevLayouts: Layouts) => ({
                ...prevLayouts,
                lg: [
                  ...prevLayouts.lg,
                  {
                    i: newConfig.id,
                    x: newConfig.x,
                    y: newConfig.y,
                    w: newConfig.w,
                    h: newConfig.h,
                  },
                ],
              }));
              setWidgetConfigs(prevConfigs => [...prevConfigs, newConfig]);
            }}
          />
        </ResizableDrawer>
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            transform: 'translate(92px, 220px)',
            zIndex: 1,
            width: `${windowWidth}px`,
            height: 'calc(100vh - 250px)',
            backgroundColor: MOON_100,
          }}>
          <ResponsiveGridLayout
            layouts={{
              lg: layouts.lg,
              md: layouts.lg,
              sm: layouts.lg,
              xs: layouts.lg,
              xxs: layouts.lg,
            }}
            breakpoints={{lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0}}
            cols={{lg: 32, md: 32, sm: 32, xs: 32, xxs: 32}}
            rowHeight={32}
            margin={[0, 0]}
            containerPadding={[0, 0]}
            width={windowWidth}
            onLayoutChange={onLayoutChange}
            compactType={null}
            isResizable={true}
            isDraggable={true}
            draggableCancel=".no-drag"
            autoSize={false}
            isBounded={true}
            style={{height: '100%'}}
            allowOverlap={true}
            onDragStop={onLayoutChange}
            onResizeStop={onLayoutChange}>
            {widgetConfigs.map((config, index) => {
              // Find the corresponding layout object for this widget
              const layoutItem = (layouts.lg || []).find(
                (l: {i: string}) => l.i === config.id
              );
              // Fallback layout if not found
              const usedLayout = layoutItem || {
                i: config.id,
                x: config.x,
                y: config.y,
                w: config.w,
                h: config.h,
              };
              if (config.type === 'projectInfo') {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex items-center justify-center ">
                    <div className="flex h-[calc(100%-8px)] w-[calc(100%-8px)] gap-4 rounded border border-moon-300 bg-white p-4">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">Project visibility: </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <ProjectAccessItem
                          access={projectAccess}
                          isTeamProject={project.entity.isTeam}
                        />
                      </div>
                    </div>
                  </div>
                );
              } else if (config.type === 'owner' && project.user !== null) {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex items-center justify-center ">
                    <div
                      className="flex gap-4 rounded border border-moon-300 bg-white p-4"
                      style={{
                        width: 'calc(100% - 8px)',
                        height: 'calc(100% - 8px)',
                      }}>
                      <div className="flex items-center gap-2">
                        <span className="text-sm">Owner </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <UserLinkItem user={project.user}></UserLinkItem>
                      </div>
                    </div>
                  </div>
                );
              } else if (config.type === 'stats') {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex w-full items-center justify-center">
                    <StatsWidget project={project} />
                  </div>
                );
              } else if (config.type === 'userTraceCountsChart') {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex w-full items-center justify-center">
                    <UserTraceCountsChart
                      project={project}
                      widgetConfigs={widgetConfigs}
                      setWidgetConfigs={setWidgetConfigs}
                      userTraceCountsData={userTraceCountsData}
                      isLoading={isLoading}
                      userInfo={
                        typeof userInfo === 'object' && userInfo !== null
                          ? userInfo
                          : []
                      }
                    />
                  </div>
                );
              } else if (config.type === 'chart' && config.chartConfig) {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex items-center justify-center">
                    <CallChartsWidget
                      key={config.id}
                      callData={callData}
                      chartConfig={config.chartConfig}
                      entity={project.entityName}
                      project={project.name}
                      isLoading={isLoading}
                      filter={{} as WFHighLevelCallFilter}
                      index={index}
                      setWidgets={newWidgets =>
                        setWidgetConfigs(newWidgets as WidgetConfig[])
                      }
                      widgets={widgetConfigs}
                    />
                  </div>
                );
              }
              return null;
            })}
          </ResponsiveGridLayout>
        </div>
      </div>
    </Tailwind>
  );
};

interface UserLinkItemProps {
  user: {
    username: string;
    name: string;
    photoUrl: string | null;
  };
}

const UserLinkItem: React.FC<UserLinkItemProps> = ({user}) => {
  const {username, photoUrl, name} = user;
  const content = (
    <div className="flex items-center gap-2">
      <img
        src={photoUrl ?? '/default-profile-picture.png'}
        className="h-24 w-24 rounded-full"
        alt={name}
      />
      <span>{name}</span>
    </div>
  );

  return (
    <Link className="user-link" to={`/${username}`}>
      {content}
    </Link>
  );
};

export function getIconForProjectAccess(
  access: AccessOption,
  isTeamProject: boolean
): IconName {
  switch (access) {
    case AccessOption.Restricted:
      return 'lock-closed';
    case AccessOption.Private:
      return isTeamProject ? 'users-team' : 'lock-closed';
    case AccessOption.Public:
      return 'lock-open';
    case AccessOption.Open:
      return 'privacy-open';
  }
}
export function getDisplayNameForProjectAccess(
  access: AccessOption,
  isTeamProject: boolean
): string {
  switch (access) {
    case AccessOption.Restricted:
      return 'Restricted';
    case AccessOption.Private:
      return isTeamProject ? 'Team' : 'Private';
    case AccessOption.Public:
      return 'Public';
    case AccessOption.Open:
      return 'Open';
  }
}

export function getDescriptionForProjectAccess(
  access: AccessOption,
  isTeamProject: boolean
): string {
  switch (access) {
    case AccessOption.Restricted:
      return 'Only invited members can access this project. Public sharing is disabled.';
    case AccessOption.Private:
      return `Only ${
        isTeamProject ? `your team` : `you`
      } can view and edit this project.`;
    case AccessOption.Public:
      return `Anyone can view this project. Only ${
        isTeamProject ? `your team` : `you`
      } can edit.`;
    case AccessOption.Open:
      return `Anyone can submit runs or reports (intended for classroom projects or benchmark competitions).`;
  }
}

interface ProjectAccessItemProps {
  access: AccessOption;
  isTeamProject: boolean;
}

const ProjectAccessItem: React.FC<ProjectAccessItemProps> = ({
  access,
  isTeamProject,
}) => {
  const iconName = getIconForProjectAccess(access, isTeamProject);
  return (
    <Tailwind>
      <div className="flex items-center">
        {iconName && <Icon name={iconName} />}
        <span className="ml-6">
          {getDisplayNameForProjectAccess(access, isTeamProject)}
        </span>
      </div>
    </Tailwind>
  );
};

interface StatsWidgetProps {
  project: Project;
}

const StatsWidget: React.FC<StatsWidgetProps> = ({project}) => {
  const {useCallsStats} = useWFHooks();
  const {result, loading: callsStatsLoading} = useCallsStats({
    entity: project.entityName,
    project: project.name,
  });

  const {
    value: projectStats,
    loading: projectStatsLoading,
    error: projectStatsError,
  } = useProjectStats(
    projectIdFromParts({entity: project.entityName, project: project.name})
  );

  const traceCount = useMemo(
    () => (
      <div>
        {callsStatsLoading ? (
          <LoadingDots />
        ) : (
          result?.count.toLocaleString() ?? 0
        )}
      </div>
    ),
    [callsStatsLoading, result]
  );

  const [
    totalIngestionSize,
    objectsIngestionSize,
    tablesIngestionSize,
    filesIngestionSize,
  ] = useMemo(() => {
    if (projectStatsLoading) {
      return Array(4).fill(<LoadingDots />);
    }
    return [
      convertBytes(projectStats?.trace_storage_size_bytes ?? 0),
      convertBytes(projectStats?.objects_storage_size_bytes ?? 0),
      convertBytes(projectStats?.tables_storage_size_bytes ?? 0),
      convertBytes(projectStats?.files_storage_size_bytes ?? 0),
    ];
  }, [projectStatsLoading, projectStats]);

  return (
    <React.Fragment>
      {projectStatsError ? (
        <p className="text-red-500">Error loading storage sizes</p>
      ) : (
        <div
          className="grid grid-cols-[150px_1fr] rounded border border-moon-300 bg-white p-4 [&>*:nth-child(odd)]:text-moon-400"
          style={{
            width: 'calc(100% - 8px)',
            height: 'calc(100% - 8px)',
          }}>
          <div>Total traces</div>
          <div>{traceCount}</div>
          <div>Traces ingestion size</div>
          <div>{totalIngestionSize}</div>
          <div>Objects ingestion size</div>
          <div>{objectsIngestionSize}</div>
          <div>Tables ingestion size</div>
          <div>{tablesIngestionSize}</div>
          <div>Files ingestion size</div>
          <div>{filesIngestionSize}</div>
        </div>
      )}
    </React.Fragment>
  );
};

const CallChartsWidget: React.FC<{
  callData: ExtractedCallData[];
  chartConfig: ChartConfig;
  entity: string;
  project: string;
  isLoading: boolean;
  filter: WFHighLevelCallFilter;
  index: number;
  setWidgets: (widgets: Array<React.ReactNode>) => void;
  widgets: Array<React.ReactNode>;
}> = ({
  callData,
  chartConfig: chart,
  entity,
  project,
  isLoading,
  filter,
  index,
  setWidgets,
  widgets,
}) => {
  const yField = chartAxisFields.find(f => f.key === chart.yAxis);
  const baseTitle = yField ? yField.label : chart.yAxis;
  const chartTitle = baseTitle;
  return (
    <div className=" w-[calc(100%-8px)]">
      <Chart
        key={chart.id}
        data={callData}
        height={280}
        xAxis={chart.xAxis}
        yAxis={chart.yAxis}
        plotType={chart.plotType || 'scatter'}
        binCount={chart.binCount}
        aggregation={chart.aggregation}
        title={chartTitle}
        customName={chart.customName}
        chartId={chart.id}
        entity={entity}
        project={project}
        groupKeys={chart.groupKeys}
        isLoading={isLoading}
        onRemove={() => {
          console.log('remove', index);
          setWidgets(widgets.filter((_, i) => i !== index));
        }}
        filter={filter}
      />
    </div>
  );
};

type UserInfo = {
  id: string;
  name?: string;
  photoUrl?: string;
};

// Add UserTraceCountsChart component (move above usage)
type UserTraceCountsChartProps = {
  project: Project;
  widgetConfigs: WidgetConfig[];
  setWidgetConfigs: (configs: WidgetConfig[]) => void;
  userTraceCountsData: any[];
  isLoading: boolean;
  userInfo: UserInfo[];
};
const UserTraceCountsChart: React.FC<UserTraceCountsChartProps> = ({
  project,
  widgetConfigs,
  setWidgetConfigs,
  userTraceCountsData,
  isLoading,
  userInfo,
}) => {
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [isChartHovered, setIsChartHovered] = React.useState(false);
  const [hintValue, setHintValue] = React.useState<any>(null);
  const chartHeight = isFullscreen ? window.innerHeight : 280;
  const chartWidth = isFullscreen ? window.innerWidth : 'calc(100% - 8px)';

  // Prepare data for react-vis
  const barData = userTraceCountsData.map(d => ({
    x: d.user,
    y: d.count,
    userObj: d.userObj, // pass through if available
  }));

  const chartContent = (
    <div
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 6,
        background: '#fff',
        display: 'flex',
        flexDirection: 'column',
        height: chartHeight,
        width: chartWidth || '100%',
        minHeight: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        overflow: 'hidden',
        zIndex: isFullscreen ? 1001 : 'auto',
        flexShrink: 0,
      }}
      onMouseEnter={() => setIsChartHovered(true)}
      onMouseLeave={() => setIsChartHovered(false)}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontWeight: 500,
          userSelect: 'none',
          position: 'relative',
          height: 32,
          flex: '0 0 auto',
        }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 0,
          }}>
          <span
            style={{
              fontWeight: 600,
              fontSize: isFullscreen ? 20 : 13,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              pointerEvents: 'none',
              maxWidth: 'calc(100% - 60px)',
            }}>
            User Trace Counts
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 2,
            flex: '0 0 auto',
            zIndex: 1,
            marginLeft: 'auto',
            marginRight: isFullscreen ? 8 : 4,
            marginTop: isFullscreen ? 24 : 0,
            opacity: isChartHovered || isFullscreen ? 1 : 0,
            transition: 'opacity 0.2s ease-in-out',
          }}>
          <Button
            className="no-drag"
            icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
            variant="ghost"
            size={isFullscreen ? 'large' : 'small'}
            onClick={() => setIsFullscreen(f => !f)}
          />
          <Button
            className="no-drag"
            icon="close"
            variant="ghost"
            size="small"
            onClick={() => {
              setWidgetConfigs(
                widgetConfigs.filter(c => c.type !== 'userTraceCountsChart')
              );
            }}
          />
        </div>
      </div>
      {isLoading ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: 200,
          }}>
          <WaveLoader size="small" />
        </div>
      ) : barData.length === 0 ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#8F8F8F',
            fontSize: '14px',
          }}>
          No data could be found
        </div>
      ) : (
        <div style={{flex: 1, minHeight: 40, minWidth: 40}}>
          <FlexibleXYPlot
            xType="ordinal"
            margin={{left: 60, right: 20, top: 20, bottom: 60}}
            onMouseLeave={() => setHintValue(null)}>
            <XAxis
              tickLabelAngle={0}
              tickFormat={(userId: string) => {
                const user = (userInfo ?? []).find(u => u.id === userId);
                return user ? user.name ?? userId : userId;
              }}
            />
            <YAxis />
            <VerticalBarSeries
              data={barData}
              color={TEAL_600}
              barWidth={0.8} // Add padding between bars
              onValueMouseOver={v => setHintValue(v)}
              onValueMouseOut={() => setHintValue(null)}
            />
            {hintValue && (
              <Hint value={hintValue}>
                <div
                  style={{
                    background: '#fff',
                    border: '1px solid #ccc',
                    padding: 8,
                    borderRadius: 4,
                    fontSize: 12,
                  }}>
                  <div>
                    <b>User:</b>{' '}
                    {hintValue.x ? (
                      <UserLink userId={hintValue.x} includeName={true} />
                    ) : (
                      hintValue.x
                    )}
                  </div>
                  <div>
                    <b>Traces:</b> {hintValue.y}
                  </div>
                </div>
              </Hint>
            )}
          </FlexibleXYPlot>
        </div>
      )}
    </div>
  );

  if (isFullscreen) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 40,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}
        onClick={e => {
          if (e.target === e.currentTarget) {
            setIsFullscreen(false);
          }
        }}>
        {chartContent}
      </div>
    );
  }

  return chartContent;
};

export const WeaveOnlyOverview = ({
  project,
  projectAccess,
}: {
  project: Project;
  projectAccess: AccessOption;
}) => {
  return (
    <ApolloProvider client={makeGorillaApolloClient()}>
      <WeaveOnlyOverviewInner project={project} projectAccess={projectAccess} />
    </ApolloProvider>
  );
};
