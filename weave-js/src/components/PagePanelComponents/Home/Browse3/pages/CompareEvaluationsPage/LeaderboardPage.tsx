
import React from 'react';

import {SimplePageLayout} from '../common/SimplePageLayout';

type LeaderboardPageProps = {
  entity: string;
  project: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  return (
    <SimplePageLayout
      title="Leaderboard"
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: (
            <LeaderboardPageContent
              entity={props.entity}
              project={props.project}
            />
          ),
        },
      ]}
    />
  );
};

export const LeaderboardPageContent: React.FC<
  LeaderboardPageProps
> = props => {
  return <>Leaderboard</>;
};
