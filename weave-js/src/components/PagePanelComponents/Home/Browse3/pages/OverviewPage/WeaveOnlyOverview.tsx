import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  projectIdFromParts,
  useProjectStats,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {convertBytes} from '@wandb/weave/util';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import React, {useMemo} from 'react';
import {Link} from 'react-router-dom';

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
    <Tailwind>
      <div className="flex flex-col px-32 py-8">
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

        {project.user !== null && (
          <div className="flex gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm">Owner</span>
            </div>
            <div className="flex items-center gap-2">
              <UserLinkItem user={project.user}></UserLinkItem>
            </div>
          </div>
        )}

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
