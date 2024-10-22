import React from 'react';

export const LeaderboardPage: React.FC<{
  entity: string;
  project: string;
  leaderboardName: string;
}> = ({entity, project, leaderboardName}) => {
  return <div>LeaderboardPage: {entity} {project} {leaderboardName}</div>;
};
