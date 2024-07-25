import {IconNames} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import {useMemo} from 'react';

import {FancyPageSidebarItem} from './FancyPageSidebar';

export const useProjectSidebar = (
  isLoading: boolean,
  viewingRestricted: boolean,
  hasModelsData: boolean,
  hasWeaveData: boolean,
  isLargeWorkspaceModeEnabled: boolean,
  hasTraceBackend: boolean = true
): FancyPageSidebarItem[] => {
  // Should show models sidebar items if we have models data or if we don't have a trace backend
  const showModelsSidebarItems = hasModelsData || !hasTraceBackend;
  // Should show weave sidebar items if we have weave data and we have a trace backend
  const showWeaveSidebarItems = hasWeaveData && hasTraceBackend;

  const isModelsOnly = showModelsSidebarItems && !showWeaveSidebarItems;
  const isWeaveOnly = !showModelsSidebarItems && showWeaveSidebarItems;

  const isNoSidebarItems = !showModelsSidebarItems && !showWeaveSidebarItems;
  const isBothSidebarItems = showModelsSidebarItems && showWeaveSidebarItems;
  const isShowAll = isNoSidebarItems || isBothSidebarItems;
  return useMemo(() => {
    const allItems = isLoading
      ? []
      : [
          {
            type: 'label' as const,
            label: 'Models',
            isShown: isShowAll,
          },
          {
            type: 'button' as const,
            name: 'Overview',
            slug: 'overview',
            isShown: !isWeaveOnly,
            isDisabled: false,
            iconName: IconNames.Info,
          },
          {
            type: 'button' as const,
            name: 'Workspace',
            slug: 'workspace',
            isShown: !isWeaveOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.DashboardBlackboard,
          },
          {
            type: 'button' as const,
            name: 'Runs',
            slug: 'table',
            isShown: !isWeaveOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.Table,
          },
          {
            type: 'button' as const,
            name: 'Charts',
            slug: 'charts',
            isShown: isLargeWorkspaceModeEnabled && isModelsOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.ChartVerticalBars,
          },
          {
            type: 'button' as const,
            name: 'Jobs',
            slug: 'jobs',
            isShown: isModelsOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.FlashBolt,
          },
          {
            type: 'button' as const,
            name: 'Automat.', // Truncation per design
            nameTooltip: 'Automations',
            slug: 'automations',
            isShown: isModelsOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.JobAutomation,
          },
          {
            type: 'button' as const,
            name: 'Sweeps',
            slug: 'sweeps',
            isShown: isModelsOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.SweepsBroom,
          },
          {
            type: 'button' as const,
            name: 'Reports',
            slug: 'reportlist',
            isShown: !isWeaveOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.Report,
          },
          {
            type: 'button' as const,
            name: 'Artifacts',
            slug: 'artifacts',
            isShown: isModelsOnly,
            iconName: IconNames.VersionsLayers,
            isDisabled: viewingRestricted,
          },
          {
            type: 'menuPlaceholder' as const,
            isShown: isShowAll,
            key: 'moreModels',
            menu: ['charts', 'jobs', 'automations', 'sweeps', 'artifacts'],
          },
          // Remember to hide weave if env is not prod
          // {
          //   type: 'button' as const,
          //   name: 'Weave',
          //   slug: 'weave',
          //   isShown: !showWeaveSidebarItems,
          //   iconName: IconNames.CodeAlt,
          //   isDisabled: viewingRestricted,
          // },
          {
            type: 'divider' as const,
            key: 'dividerModelsWeave',
            isShown: isShowAll,
          },
          {
            type: 'label' as const,
            label: 'Weave',
            isShown: isShowAll,
          },
          {
            type: 'button' as const,
            name: 'Evaluations',
            slug: 'weave/evaluations',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.TypeBoolean,
            // path: baseRouter.callsUIUrl(entity, project, evaluationsFilter),
          },
          {
            type: 'button' as const,
            name: 'Models',
            slug: 'weave/models',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.Model,
          },
          {
            type: 'button' as const,
            name: 'Datasets',
            slug: 'weave/datasets',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.Table,
          },
          {
            type: 'divider' as const,
            key: 'dividerWithinWeave',
            isShown: isWeaveOnly,
          },
          {
            type: 'button' as const,
            name: 'Traces',
            slug: 'weave/traces',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.LayoutTabs,
            // path: baseRouter.callsUIUrl(entity, project, {
            //   traceRootsOnly: true,
            // }),
          },
          {
            type: 'button' as const,
            name: 'Operations',
            slug: 'weave/operations',
            additionalSlugs: ['weave/op-versions'],
            isShown: isWeaveOnly,
            iconName: IconNames.JobProgramCode,
          },
          {
            type: 'button' as const,
            name: 'Objects',
            slug: 'weave/objects',
            additionalSlugs: ['weave/object-versions'],
            isShown: isWeaveOnly,
            iconName: IconNames.CubeContainer,
          },
          {
            type: 'menuPlaceholder' as const,
            // name: 'More',
            // slug: 'moreWeave',
            key: 'moreWeave',
            isShown: isShowAll,
            // iconName: IconNames.OverflowHorizontal,
            menu: ['weave/operations', 'weave/objects'],
          },
        ];

    const indexedItems = _.keyBy(allItems, 'slug');

    // Expand menu items
    const expandedItems = allItems.map(item => {
      if (item.type !== 'menuPlaceholder') {
        return item;
      }
      // TODO: Probably need to filter this by shown too
      return {
        ...item,
        type: 'menu',
        menu: item.menu.map(menuItemId => indexedItems[menuItemId]),
      };
    });

    // Filter out items that are not shown.
    const onlyShownItems = expandedItems
      .filter(({isShown}) => isShown)
      .map(({isShown, ...item}) => item) as FancyPageSidebarItem[];

    return onlyShownItems;
  }, [
    isLoading,
    isLargeWorkspaceModeEnabled,
    isModelsOnly,
    isWeaveOnly,
    showWeaveSidebarItems,
    isShowAll,
    viewingRestricted,
  ]);
};
