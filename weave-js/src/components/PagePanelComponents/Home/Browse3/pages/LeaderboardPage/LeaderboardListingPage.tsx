import React from 'react';

export const LeaderboardListingPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  return (
    <div>
      LeaderboardListingPage: {entity} {project}
    </div>
  );
};
