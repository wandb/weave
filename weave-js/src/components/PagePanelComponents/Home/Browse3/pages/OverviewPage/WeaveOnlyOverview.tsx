import {ApolloProvider} from '@apollo/client';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {MOON_100} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {useUsers} from '@wandb/weave/components/UserLink';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';
import {Layouts, Responsive as ResponsiveGridLayout} from 'react-grid-layout';

import {useLocalStorage} from '../../../../../../util/useLocalStorage';
import {CallsCharts} from '../../charts/CallsCharts';
import {ChartConfig} from '../../charts/types';
import {useChartsData} from '../../charts/useChartsData';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';
import {DEFAULT_FILTER_CALLS} from '../CallsPage/callsTableQuery';
import {ResizableDrawer} from '../common/ResizableDrawer';
import CallChartsWidget from './CallChartsWidget';
import CostsBarChart from './CostsBarChart';
import ProjectAccessItem from './ProjectAccessItem';
import StatsWidget from './StatsWidget';
import UserLinkItem from './UserLinkItem';
import UserTraceCountsChart from './UserTraceCountsChart';

export enum AccessOption {
  Restricted = 'RESTRICTED',
  Private = 'PRIVATE',
  Public = 'USER_READ',
  Open = 'USER_WRITE',
}

type WidgetConfig = {
  id: string;
  type:
    | 'projectInfo'
    | 'owner'
    | 'stats'
    | 'chart'
    | 'userTraceCountsChart'
    | 'costsBarChart';
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
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

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

  // Calculate costs by user
  const costsData = useMemo(() => {
    if (!callData) return [];

    // Create a map of user costs
    const userCosts = new Map<string, {totalCost: number; callCount: number}>();

    // Process call data to calculate costs per user
    callData.forEach(call => {
      if (!call.wb_user_id) return;

      const userId = call.wb_user_id;
      const existing = userCosts.get(userId) || {totalCost: 0, callCount: 0};

      // Use actual cost data from the call (since includeCosts: true is set)
      const callCost = call.cost || 0;

      userCosts.set(userId, {
        totalCost: existing.totalCost + callCost,
        callCount: existing.callCount + 1,
      });
    });

    // Convert to array format
    return Array.from(userCosts.entries())
      .map(([user, data]) => ({
        user,
        totalCost: data.totalCost,
        callCount: data.callCount,
      }))
      .sort((a, b) => b.totalCost - a.totalCost);
  }, [callData]);

  // Prepare data for the Chart widget (must match ExtractedCallData[] type)
  const userTraceCountsData = useMemo(
    () =>
      Object.entries(userTraceCounts)
        .map(([user, count]) => ({
          callId: user, // Use user as unique id
          traceId: '',
          started_at: '',
          wb_user_id: user,
          user, // for xAxis
          count: count as number, // for yAxis
        }))
        .sort((a, b) => b.count - a.count), // Sort descending by count
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
  const hasCostsBarChart = widgetConfigs.some(w => w.type === 'costsBarChart');

  const addUserTraceCountsChartWidget = () => {
    if (hasUserTraceCountsChart) return;
    const newConfig: WidgetConfig = {
      id: 'userTraceCountsChart',
      type: 'userTraceCountsChart',
      x: 0,
      y: 6,
      w: 11,
      h: 10,
      minH: 10,
      maxH: 10,
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

  const addCostsBarChartWidget = () => {
    if (hasCostsBarChart) return;
    const newConfig: WidgetConfig = {
      id: 'costsBarChart',
      type: 'costsBarChart',
      x: 0,
      y: 15,
      w: 11,
      h: 10,
      minH: 10,
      maxH: 10,
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
        {/* Floating action buttons bottom right */}
        <div
          style={{
            position: 'fixed',
            bottom: 16,
            right: 36,
            zIndex: 30,
            display: 'flex',
            gap: 16,
          }}>
          {/* Conditional add-new button: menu if charts missing, direct action if both present */}
          {hasUserTraceCountsChart && hasCostsBarChart ? (
            // Both charts are present, open call charts directly
            <Button
              icon="add-new"
              variant="primary"
              size="large"
              tooltip="Open Call Charts"
              onClick={() => setShowChartsDrawer(true)}
              className="no-drag rounded-full shadow-lg"
            />
          ) : (
            // At least one chart is missing, show dropdown menu
            <DropdownMenu.Root
              open={isDropdownOpen}
              onOpenChange={setIsDropdownOpen}>
              <DropdownMenu.Trigger>
                <Button
                  icon="add-new"
                  variant="primary"
                  size="large"
                  tooltip="Add Chart"
                  className="no-drag rounded-full shadow-lg"
                />
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  side="top"
                  className="z-[10000000]"
                  style={{zIndex: 10000000}}>
                  <DropdownMenu.Item
                    onClick={() => {
                      setShowChartsDrawer(true);
                      setIsDropdownOpen(false);
                    }}>
                    <Icon name="chart-scatterplot" />
                    Open Call Charts
                  </DropdownMenu.Item>
                  {!hasUserTraceCountsChart && (
                    <DropdownMenu.Item
                      onClick={() => {
                        addUserTraceCountsChartWidget();
                        setIsDropdownOpen(false);
                      }}>
                      <Icon name="chart-vertical-bars" />
                      Add User Trace Counts Chart
                    </DropdownMenu.Item>
                  )}
                  {!hasCostsBarChart && (
                    <DropdownMenu.Item
                      onClick={() => {
                        addCostsBarChartWidget();
                        setIsDropdownOpen(false);
                      }}>
                      <Icon name="chart-vertical-bars" />
                      Add Costs Bar Chart
                    </DropdownMenu.Item>
                  )}
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          )}
        </div>
        {/* End floating action buttons */}
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
                w: 10,
                h: 10,
                minH: 10,
                maxH: 10,
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
            transform: 'translate(92px, 200px)',
            zIndex: 1,
            width: `${windowWidth}px`,
            height: 'calc(100vh - 210px)',
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
            rowHeight={24}
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
                    <div className="flex h-[calc(100%-8px)] w-[calc(100%-8px)] gap-8 rounded border border-moon-300 bg-white p-4">
                      <div className="flex w-[100px] items-center">
                        <span className="text-sm">Project visibility: </span>
                      </div>
                      <div className="flex items-center">
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
                      className="flex gap-8 rounded border border-moon-300 bg-white p-4"
                      style={{
                        width: 'calc(100% - 8px)',
                        height: 'calc(100% - 8px)',
                      }}>
                      <div className="flex w-[100px] items-center">
                        <span className="text-sm">Owner: </span>
                      </div>
                      <div className="flex items-center">
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
              } else if (config.type === 'costsBarChart') {
                return (
                  <div
                    key={config.id}
                    data-grid={usedLayout}
                    className="flex w-full items-center justify-center">
                    <CostsBarChart
                      project={project}
                      widgetConfigs={widgetConfigs}
                      setWidgetConfigs={setWidgetConfigs}
                      costsData={costsData}
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
