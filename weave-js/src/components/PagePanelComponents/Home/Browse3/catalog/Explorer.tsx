import React from 'react';

import {ExplorerLoaded} from './ExplorerLoaded';
import {MODEL_INFO} from './modelInfo';

type ExplorerProps = {
  collectionId?: string;
  // If true, we should create the default target project when navigating to the playground.
  shouldCreateProject: boolean;
};

export const Explorer = ({
  collectionId,
  shouldCreateProject,
}: ExplorerProps) => {
  return (
    <ExplorerLoaded
      modelInfo={MODEL_INFO}
      collectionId={collectionId}
      shouldCreateProject={shouldCreateProject}
    />
  );
};
