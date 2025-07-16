import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {AccessOption} from './WeaveOnlyOverview';

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

export interface ProjectAccessItemProps {
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

export default ProjectAccessItem;
