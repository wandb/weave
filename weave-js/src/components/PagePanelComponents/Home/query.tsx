// This file contains the primary data fetch for the Home page.

import * as w from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';

type EngineEnvironmentType = 'wandb' | 'local' | 'colab';
/**
 *
 */
const getEngineEnvironment = (): EngineEnvironmentType => {
  return 'wandb';
};

/**
 * Fetches the recent boards for the current user.
 */
const getRecentBoards = () => {
  return [];
};

/**
 * Fetches the recent tables for the current user.
 */
const getRecentTables = () => {
  return [];
};

/**
 * Fetches the user entities.
 */
export const useUserName = (): {
  result: string | undefined;
  loading: boolean;
} => {
  const entityNameNode = w.opUserUsername({
    user: w.opRootViewer({}),
  });
  return useNodeValue(entityNameNode);
};

/**
 * Fetches the user's entities.
 */
export const useUserEntities = (): {
  result: string[];
  loading: boolean;
} => {
  const entityNamesNode = w.opEntityName({
    entity: w.opUserEntities({entity: w.opRootViewer({})}),
  });
  const entityNameValue = useNodeValue(entityNamesNode);
  return useMemo(
    () => ({
      result: entityNameValue.result ?? [],
      loading: entityNameValue.loading,
    }),
    [entityNameValue.loading, entityNameValue.result]
  );
};

export const useProjectsForEntityWithWeaveObject = (
  entityName: string
): {
  result: string[];
  loading: boolean;
} => {
  const projectsNode = w.opEntityProjects({
    entity: w.opRootEntity({
      entityName: w.constString(entityName),
    }),
  });
  // TODO: filter to just projects that have weave objects
  const entityProjectNamesNode = w.opProjectName({
    project: projectsNode,
  });
  const entityProjectNamesValue = useNodeValue(entityProjectNamesNode);
  return useMemo(
    () => ({
      result: entityProjectNamesValue.result ?? [],
      loading: entityProjectNamesValue.loading,
    }),
    [entityProjectNamesValue.loading, entityProjectNamesValue.result]
  );
};
