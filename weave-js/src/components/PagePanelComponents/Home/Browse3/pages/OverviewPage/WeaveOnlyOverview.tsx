import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  projectIdFromParts,
  useProjectStats,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {MOON_100} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {convertBytes} from '@wandb/weave/util';
import {Icon, IconName} from '@wandb/weave/components/Icon';

import React, {useMemo, useState, useEffect} from 'react';
import {Link} from 'react-router-dom';
import {Responsive as ResponsiveGridLayout, Layouts} from 'react-grid-layout';

import {useLocalStorage} from '../../../../../../util/useLocalStorage';
import {ResizableDrawer} from '../common/ResizableDrawer';
import {CallsCharts} from '../../charts/CallsCharts';
import {DEFAULT_FILTER_CALLS} from '../CallsPage/callsTableQuery';
import {WFHighLevelCallFilter} from '../CallsPage/callsTableFilter';

export enum AccessOption {
  Restricted = 'RESTRICTED',
  Private = 'PRIVATE',
  Public = 'USER_READ',
  Open = 'USER_WRITE',
}

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

export const WeaveOnlyOverview: React.FC<{
  project: Project;
  projectAccess: AccessOption;
}> = ({project, projectAccess}) => {
  const [showChartsDrawer, setShowChartsDrawer] = useState(false);

  // Local storage key for layout
  const layoutKey = `weave-overview-layout-${project.name}`;
  const defaultLayouts: Layouts = {
    lg: [
      {i: 'projectInfo', x: 0, y: 0, w: 6, h: 2},
      {i: 'owner', x: 6, y: 0, w: 6, h: 2},
      {i: 'stats', x: 0, y: 2, w: 12, h: 4},
    ],
    md: [
      {i: 'projectInfo', x: 0, y: 0, w: 5, h: 2},
      {i: 'owner', x: 5, y: 0, w: 5, h: 2},
      {i: 'stats', x: 0, y: 2, w: 10, h: 4},
    ],
    sm: [
      {i: 'projectInfo', x: 0, y: 0, w: 3, h: 2},
      {i: 'owner', x: 3, y: 0, w: 3, h: 2},
      {i: 'stats', x: 0, y: 2, w: 6, h: 4},
    ],
    xs: [
      {i: 'projectInfo', x: 0, y: 0, w: 2, h: 2},
      {i: 'owner', x: 0, y: 2, w: 2, h: 2},
      {i: 'stats', x: 0, y: 4, w: 2, h: 4},
    ],
    xxs: [
      {i: 'projectInfo', x: 0, y: 0, w: 2, h: 2},
      {i: 'owner', x: 0, y: 2, w: 2, h: 2},
      {i: 'stats', x: 0, y: 4, w: 2, h: 4},
    ],
  };
  const [layouts, setLayouts] = useLocalStorage<Layouts>(
    layoutKey,
    defaultLayouts
  );

  const onLayoutChange = (newLayout: any, allLayouts: Layouts) => {
    setLayouts(allLayouts);
  };

  const defaultWidgets = [
    <div
      key="projectInfo"
      className="rounded border border-moon-300 bg-white p-4">
      <div className="flex gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm">Project visibility</span>
        </div>
        <div className="flex items-center gap-2">
          <ProjectAccessItem
            access={projectAccess}
            isTeamProject={project.entity.isTeam}
          />
        </div>
      </div>
    </div>,
    project.user !== null ? (
      <div key="owner" className="rounded border border-moon-300 bg-white p-4">
        <div className="flex gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm">Owner</span>
          </div>
          <div className="flex items-center gap-2">
            <UserLinkItem user={project.user}></UserLinkItem>
          </div>
        </div>
      </div>
    ) : null,
    <div key="stats" className="rounded border border-moon-300 bg-white p-4">
      <StatsWidget project={project} />
    </div>,
  ];

  // Store allowOverlap in local storage
  const [widgets, setWidgets] = useLocalStorage<Array<React.ReactNode>>(
    `${layoutKey}-widgets`,
    defaultWidgets
  );

  // Track window width for ResponsiveGridLayout
  const [windowWidth, setWindowWidth] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth - 32 - 60 - 32 : 1024
  );
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Tailwind className="h-full min-h-screen w-full">
      <div className="mx-32 my-8">
        <button
          className="absolute right-8 top-8 z-20 rounded border border-moon-300 bg-white px-4 py-2 text-xs text-moon-400 hover:bg-moon-200"
          onClick={() => setShowChartsDrawer(true)}>
          Open Call Charts
        </button>
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
              console.log('addChart', chart);
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
            layouts={layouts}
            breakpoints={{lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0}}
            cols={{lg: 32, md: 32, sm: 32, xs: 32, xxs: 32}}
            rowHeight={32}
            margin={[0, 0]}
            containerPadding={[0, 0]}
            width={windowWidth}
            onLayoutChange={onLayoutChange}
            verticalCompact={false}
            horizontalCompact={false}
            isResizable={true}
            isDraggable={true}
            autoSize={false}
            isBounded={true}
            style={{height: '100%'}}
            allowOverlap={true}>
            {widgets.map((widget, index) => widget)}
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
        <div className="grid w-min grid-cols-[150px_1fr] [&>*:nth-child(odd)]:text-moon-400">
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
