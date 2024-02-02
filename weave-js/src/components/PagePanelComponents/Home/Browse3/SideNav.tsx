import {IconNames} from '@wandb/weave/components/Icon';
import React, {useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {useWeaveflowRouteContext} from './context';
import {useURLSearchParamsDict} from './pages/util';
import {refDictToRefString} from './pages/wfInterface/naive';
import {Sidebar, SidebarItem} from './Sidebar';

export const SideNav = () => {
  const params = useParams<{
    entity: string;
    project: string;
    tab:
      | 'types'
      | 'type-versions'
      | 'objects'
      | 'object-versions'
      | 'ops'
      | 'op-versions'
      | 'calls'
      | 'boards'
      | 'tables';
  }>();
  const {entity, project} = params;
  const currentProject = project;
  const currentEntity = entity;
  const query = useURLSearchParamsDict();
  const filters = useMemo(() => {
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter]);
  const filterCategory = useMemo(() => {
    const category = Object.keys(filters).find(key =>
      key.toLowerCase().includes('category')
    );
    if (category === undefined) {
      return undefined;
    }
    return filters[category];
  }, [filters]);

  const selectedItemId = useMemo(() => {
    if (params.tab === 'types' || params.tab === 'type-versions') {
      return 'types';
    } else if (params.tab === 'objects' || params.tab === 'object-versions') {
      if (filterCategory === 'model') {
        return 'models';
      } else if (filterCategory === 'dataset') {
        return 'datasets';
      }
      return 'objects';
    } else if (params.tab === 'ops' || params.tab === 'op-versions') {
      return 'ops';
    } else if (params.tab === 'calls') {
      if (filterCategory === 'evaluate') {
        return 'evaluation';
      }
      return 'calls';
    }
    return null;
  }, [params.tab, filterCategory]);

  const {baseRouter} = useWeaveflowRouteContext();
  if (!currentProject || !currentEntity) {
    return null;
  }

  const items: SidebarItem[][] = [
    [
      {
        id: 'evaluation',
        name: 'Evaluations',
        iconName: IconNames.TypeNumber,
        path: baseRouter.callsUIUrl(entity, project, {
          opCategory: 'evaluate',
          opVersionRefs: [
            refDictToRefString({
              entity: currentEntity,
              project: currentProject,
              artifactName: 'Evaluation-evaluate',
              versionCommitHash: '*',
              filePathParts: [],
              refExtraTuples: [],
            }),
          ],
          isPivot: true,
        }),
      },
      {
        id: 'models',
        name: 'Models',
        iconName: IconNames.Model,
        path: baseRouter.objectVersionsUIUrl(entity, project, {
          typeCategory: 'model',
          latest: true,
        }),
      },
      {
        id: 'datasets',
        name: 'Datasets',
        iconName: IconNames.Table,
        path: baseRouter.objectVersionsUIUrl(entity, project, {
          typeCategory: 'dataset',
          latest: true,
        }),
      },
    ],
    [
      {
        id: 'ops',
        name: 'Operations',
        iconName: IconNames.JobProgramCode,
        path: baseRouter.opVersionsUIUrl(entity, project, {
          isLatest: true,
        }),
      },
      {
        id: 'calls',
        name: 'Calls',
        iconName: IconNames.RunningRepeat,
        path: baseRouter.callsUIUrl(entity, project, {
          traceRootsOnly: true,
        }),
      },
      {
        id: 'objects',
        name: 'Objects',
        iconName: IconNames.CubeContainer,
        path: baseRouter.objectVersionsUIUrl(entity, project, {
          latest: true,
        }),
      },
    ],
  ];

  return <Sidebar items={items} selectedItem={selectedItemId} />;
};
