import React from 'react';

type ThreadsPageProps = {
  entity: string;
  project: string;
  threadId?: string;
};

export const ThreadsPage = ({entity, project, threadId}: ThreadsPageProps) => {
  return (
    <div>
      ThreadsPage: {entity} {project} {threadId}
    </div>
  );
};
