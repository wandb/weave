import {IconNames} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {useParams} from 'react-router-dom';

import {useWeaveflowRouteContext} from './context';
import {useEvaluationsFilter} from './pages/CallsPage/evaluationsFilter';
import {useURLSearchParamsDict} from './pages/util';
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

  const evaluationsFilter = useEvaluationsFilter(currentEntity, currentProject);

  const selectedItemId = useMemo(() => {
    const category = Object.keys(filters).find(key =>
      key.includes('baseObjectClass')
    );
    let filterCategory;
    if (category !== undefined) {
      filterCategory = filters[category];
    }

    if (params.tab === 'types' || params.tab === 'type-versions') {
      return 'types';
    } else if (params.tab === 'objects' || params.tab === 'object-versions') {
      if (filterCategory === 'Model') {
        return 'models';
      } else if (filterCategory === 'Dataset') {
        return 'datasets';
      }
      return 'objects';
    } else if (params.tab === 'ops' || params.tab === 'op-versions') {
      return 'ops';
    } else if (params.tab === 'calls') {
      if (_.isEqual(filters, evaluationsFilter)) {
        return 'evaluation';
      }
      return 'calls';
    }
    return null;
  }, [evaluationsFilter, filters, params.tab]);

  const {baseRouter} = useWeaveflowRouteContext();
  if (!currentProject || !currentEntity) {
    return null;
  }

  const items: SidebarItem[][] = [
    [
      {
        id: 'evaluation',
        name: 'Evaluations',
        iconName: IconNames.TypeBoolean,
        path: baseRouter.callsUIUrl(entity, project, evaluationsFilter),
      },
      {
        id: 'models',
        name: 'Models',
        iconName: IconNames.Model,
        path: baseRouter.objectVersionsUIUrl(entity, project, {
          baseObjectClass: 'Model',
        }),
      },
      {
        id: 'datasets',
        name: 'Datasets',
        iconName: IconNames.Table,
        path: baseRouter.objectVersionsUIUrl(entity, project, {
          baseObjectClass: 'Dataset',
        }),
      },
    ],
    [
      {
        id: 'calls',
        name: 'Traces',
        iconName: IconNames.LayoutTabs,
        path: baseRouter.callsUIUrl(entity, project, {
          traceRootsOnly: true,
        }),
      },
      {
        id: 'ops',
        name: 'Operations',
        iconName: IconNames.JobProgramCode,
        path: baseRouter.opVersionsUIUrl(entity, project, {}),
      },
      {
        id: 'objects',
        name: 'Objects',
        iconName: IconNames.CubeContainer,
        path: baseRouter.objectVersionsUIUrl(entity, project, {}),
      },
    ],
  ];

  return <Sidebar items={items} selectedItem={selectedItemId} />;
};
