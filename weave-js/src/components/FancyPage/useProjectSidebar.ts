import {IconNames} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import {useMemo} from 'react';
import {useLocation} from 'react-router-dom';

import {FancyPageSidebarItem} from './FancyPageSidebar';

export const useProjectSidebar = (
  isLoading: boolean,
  viewingRestricted: boolean,
  hasModelsData: boolean,
  hasWeaveData: boolean,
  hasTraceBackend: boolean = true,
  hasModelsAccess: boolean = true,
  isLaunchActive: boolean = false,
  isWandbAdmin: boolean = false
): FancyPageSidebarItem[] => {
  // must preserve named workspace url query string
  // when navigating between workspace & runs pages
  let nwSearchStr: string | undefined;
  const location = useLocation();
  const allSearchParams = new URLSearchParams(location.search);
  const nwId = allSearchParams.get('nw');
  if (nwId) {
    const nwSearchParams = new URLSearchParams();
    nwSearchParams.append('nw', nwId);
    nwSearchStr = nwSearchParams.toString();
  }

  // Should show models sidebar items if we have models data or if we don't have a trace backend
  let showModelsSidebarItems = hasModelsData || !hasTraceBackend;
  // Should show weave sidebar items if we have weave data and we have a trace backend
  let showWeaveSidebarItems = hasWeaveData && hasTraceBackend;

  let isModelsOnly = showModelsSidebarItems && !showWeaveSidebarItems;
  let isWeaveOnly = !showModelsSidebarItems && showWeaveSidebarItems;

  if (!hasModelsAccess) {
    showModelsSidebarItems = false;
    isModelsOnly = false;

    showWeaveSidebarItems = true;
    isWeaveOnly = true;
  }

  const isNoSidebarItems = !showModelsSidebarItems && !showWeaveSidebarItems;
  const isBothSidebarItems = showModelsSidebarItems && showWeaveSidebarItems;
  const isShowAll = isNoSidebarItems || isBothSidebarItems;

  return useMemo(() => {
    const weaveOnlyMenu = [
      'weave/leaderboards',
      'weave/operations',
      'weave/objects',
    ];
    if (isWandbAdmin) {
      weaveOnlyMenu.push('weave/mods');
    }
    const allItems = isLoading
      ? []
      : [
          {
            type: 'button' as const,
            name: 'Overview',
            slug: 'overview',
            isShown: true,
            iconName: IconNames.Info,
          },
          {
            type: 'divider' as const,
            key: 'dividerOverview',
            isShown: isShowAll,
          },
          {
            type: 'label' as const,
            label: 'Models',
            isShown: isShowAll,
          },
          {
            type: 'button' as const,
            name: 'Workspace',
            slug: 'workspace',
            search: nwSearchStr,
            isShown: !isWeaveOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.DashboardBlackboard,
          },
          {
            type: 'button' as const,
            name: 'Runs',
            slug: 'table',
            search: nwSearchStr,
            isShown: !isWeaveOnly,
            isDisabled: viewingRestricted,
            iconName: IconNames.Table,
          },
          {
            type: 'button' as const,
            name: 'Jobs',
            slug: 'jobs',
            isShown: isModelsOnly && isLaunchActive,
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
            isShown: isModelsOnly,
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
            menu: [
              'jobs',
              'automations',
              'sweeps',
              'reportlist',
              'artifacts',
              'overview',
            ],
          },
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
            name: 'Traces',
            slug: 'weave/traces',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.LayoutTabs,
          },
          {
            type: 'button' as const,
            name: 'Evals',
            slug: 'weave/evaluations',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.BaselineAlt,
          },
          {
            type: 'button' as const,
            name: 'Playground',
            slug: 'weave/playground',
            isShown: showWeaveSidebarItems || isShowAll,
            iconName: IconNames.RobotServiceMember,
          },
          {
            type: 'button' as const,
            name: 'Prompts',
            slug: 'weave/prompts',
            isShown: isWeaveOnly,
            iconName: IconNames.ForumChatBubble,
          },
          {
            type: 'button' as const,
            name: 'Models',
            slug: 'weave/models',
            isShown: isWeaveOnly,
            iconName: IconNames.Model,
          },
          {
            type: 'button' as const,
            name: 'Datasets',
            slug: 'weave/datasets',
            isShown: isWeaveOnly,
            iconName: IconNames.Table,
          },
          {
            type: 'button' as const,
            name: 'Scorers',
            slug: 'weave/scorers',
            isShown: isWeaveOnly,
            iconName: IconNames.TypeNumberAlt,
          },
          {
            type: 'button' as const,
            name: 'Mods',
            slug: 'weave/mods',
            isShown: false, // Only shown in overflow menu
            isDisabled: !isWandbAdmin,
            iconName: IconNames.LayoutGrid,
          },
          {
            type: 'button' as const,
            name: 'Leaders',
            slug: 'weave/leaderboards',
            isShown: false, // Only shown in overflow menu
            iconName: IconNames.BenchmarkSquare,
          },
          {
            type: 'button' as const,
            name: 'Ops',
            slug: 'weave/operations',
            additionalSlugs: ['weave/op-versions'],
            isShown: false, // Only shown in overflow menu
            iconName: IconNames.JobProgramCode,
          },
          {
            type: 'button' as const,
            name: 'Objects',
            slug: 'weave/objects',
            additionalSlugs: ['weave/object-versions'],
            isShown: false, // Only shown in overflow menu
            iconName: IconNames.CubeContainer,
          },
          {
            type: 'menuPlaceholder' as const,
            key: 'moreWeaveOnly',
            isShown: isWeaveOnly,
            menu: weaveOnlyMenu,
          },
          {
            type: 'menuPlaceholder' as const,
            key: 'moreWeaveBoth',
            isShown: isShowAll,
            menu: [
              'weave/prompts',
              'weave/models',
              'weave/datasets',
              'weave/scorers',
            ].concat(weaveOnlyMenu),
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
    isLaunchActive,
    isLoading,
    isModelsOnly,
    isShowAll,
    isWandbAdmin,
    isWeaveOnly,
    nwSearchStr,
    showWeaveSidebarItems,
    viewingRestricted,
  ]);
};
