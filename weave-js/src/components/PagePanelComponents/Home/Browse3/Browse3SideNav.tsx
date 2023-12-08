import {
  AutoFixHigh,
  Category,
  DashboardCustomize,
  Dataset,
  Layers,
  ManageHistory,
  ModelTraining,
  Rule,
  Scoreboard,
  Segment,
  TableChart,
  Tune,
  TypeSpecimen,
} from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  FormControl,
  ListSubheader,
  TextField,
  Toolbar,
} from '@mui/material';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import React, {FC, Fragment, useMemo} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {useProjectsForEntity} from '../query';
import {useWeaveflowRouteContext} from './context';
import {WFHighLevelCallFilter} from './pages/CallsPage';
import {WFHighLevelObjectVersionFilter} from './pages/ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from './pages/OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from './pages/TypeVersionsPage';
import {useURLSearchParamsDict} from './pages/util';

const drawerWidth = 240;

type NavigationCallbacks = {
  navigateToProject: (project: string) => void;
  navigateToObjectVersions: (filter?: WFHighLevelObjectVersionFilter) => void;
  navigateToCalls: (filter?: WFHighLevelCallFilter) => void;
  navigateToTypeVersions: (filter?: WFHighLevelTypeVersionFilter) => void;
  navigateToOpVersions: (filter?: WFHighLevelOpVersionFilter) => void;
  navigateToBoards: (filter?: string) => void;
  navigateToTables: (filter?: string) => void;
};

type Browse3ProjectSideNavProps = {
  entity: string;
  project: string;
  selectedCategory?:
    | 'objects'
    | 'calls'
    | 'types'
    | 'ops'
    | 'boards'
    | 'tables';
  filterCategory?: string;
} & NavigationCallbacks;

export const RouteAwareBrowse3ProjectSideNav: FC = props => {
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
  const history = useHistory();
  const currentProject = params.project;
  const currentEntity = params.entity;
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
  const selectedNavSection = useMemo(() => {
    if (params.tab === 'types' || params.tab === 'type-versions') {
      return 'types';
    } else if (params.tab === 'objects' || params.tab === 'object-versions') {
      return 'objects';
    } else if (params.tab === 'ops' || params.tab === 'op-versions') {
      return 'ops';
    } else if (params.tab === 'calls') {
      return 'calls';
    } else if (params.tab === 'boards') {
      return 'boards';
    } else if (params.tab === 'tables') {
      return 'tables';
    }
    return undefined;
  }, [params.tab]);
  const filterCategory = useMemo(() => {
    const category = Object.keys(filters).find(key =>
      key.toLowerCase().includes('category')
    );
    if (category === undefined) {
      return undefined;
    }
    return filters[category];
  }, [filters]);

  const router = useWeaveflowRouteContext();
  if (!currentProject || !currentEntity) {
    return null;
  }
  return (
    <Browse3ProjectSideNav
      entity={currentEntity}
      project={currentProject}
      selectedCategory={selectedNavSection}
      filterCategory={filterCategory}
      navigateToProject={project => {
        history.push(`/${params.entity}/${project}`);
      }}
      navigateToObjectVersions={(filter?: WFHighLevelObjectVersionFilter) => {
        history.push(
          router.objectVersionsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToCalls={(filter?: WFHighLevelCallFilter) => {
        history.push(router.callsUIUrl(params.entity, params.project, filter));
      }}
      navigateToTypeVersions={(filter?: WFHighLevelTypeVersionFilter) => {
        history.push(
          router.typeVersionsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToOpVersions={(filter?: WFHighLevelOpVersionFilter) => {
        history.push(
          router.opVersionsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToBoards={(filter?: string) => {
        // TODO: Move to router
        history.push(
          `/${params.entity}/${params.project}/boards${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToTables={(filter?: string) => {
        // TODO: Move to router
        history.push(
          `/${params.entity}/${params.project}/tables${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
    />
  );
};

const Browse3ProjectSideNav: FC<Browse3ProjectSideNavProps> = props => {
  const sections = useSectionsForProject(props);
  const entityProjectsValue = useProjectsForEntity(props.entity);
  const projects = useMemo(() => {
    return [props.project, ...(entityProjectsValue.result ?? [])];
  }, [entityProjectsValue.result, props.project]);

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: drawerWidth,
          boxSizing: 'border-box',
        },
      }}>
      <Toolbar />
      <Box
        sx={{
          p: 2,
          height: 65, // manual to match sidebar
          borderBottom: '1px solid #e0e0e0',
        }}>
        <FormControl fullWidth>
          <Autocomplete
            size={'small'}
            disablePortal
            disableClearable
            options={projects}
            value={props.project}
            onChange={(event, newValue) => {
              props.navigateToProject(newValue);
            }}
            renderInput={params => <TextField {...params} label="Project" />}
          />
        </FormControl>
      </Box>
      <SideNav sections={sections} />;
    </Drawer>
  );
};

type SectionType = {
  title: string;
  items: ItemType[];
};
type ItemType = {
  title: string;
  icon: React.ReactNode;
  selected?: boolean;
  onClick: () => void;
  children?: ItemType[];
};
const SideBarNavItem: FC<{item: ItemType; depth?: number}> = props => {
  const depth = props.depth ?? 0;
  return (
    <Fragment>
      <ListItemButton
        sx={{pl: 2 + depth}}
        onClick={props.item.onClick}
        selected={props.item.selected}>
        <ListItemIcon>{props.item.icon}</ListItemIcon>
        <ListItemText primary={props.item.title} />
      </ListItemButton>
      {props.item.children && (
        <List disablePadding>
          {props.item.children.map((item, itemIndex) => {
            return (
              <SideBarNavItem item={item} depth={depth + 2} key={itemIndex} />
            );
          })}
        </List>
      )}
    </Fragment>
  );
};
const SideNav: FC<{
  sections: SectionType[];
}> = props => {
  return (
    <Box sx={{overflow: 'auto'}}>
      {props.sections.map((section, sectionIndex) => {
        return (
          <Fragment key={sectionIndex}>
            <ListSubheader
              id="nested-list-subheader"
              sx={{
                pt: 1,
              }}>
              {/* {sectionIndex !== 0 && <Divider />} */}
              {section.title}
              <Divider />
            </ListSubheader>
            <List>
              {section.items.map((item, itemIndex) => {
                return <SideBarNavItem item={item} key={itemIndex} />;
              })}
            </List>
          </Fragment>
        );
      })}
      {/* <Divider /> */}
    </Box>
  );
};

const useSectionsForProject = (props: Browse3ProjectSideNavProps) => {
  // TODO: Lookup pinned sidebar items from entity/project + user
  const sections: SectionType[] = useMemo(() => {
    return [
      {
        title: 'Records',
        items: [
          {
            title: 'Objects', // , 'Instances (ObjectVersions)',
            selected:
              props.selectedCategory === 'objects' &&
              !(
                props.filterCategory === 'model' ||
                props.filterCategory === 'dataset'
              ),
            icon: <Category />,
            onClick: () => {
              props.navigateToObjectVersions({
                latest: true,
              });
            },
            // TODO: Get Feedback from team on this
            children: [
              {
                title: 'Models',
                icon: <Layers />,
                selected: props.filterCategory === 'model',
                onClick: () => {
                  props.navigateToObjectVersions({
                    typeCategory: 'model',
                    latest: true,
                  });
                },
              },
              {
                title: 'Datasets',
                icon: <Dataset />,
                selected: props.filterCategory === 'dataset',
                onClick: () => {
                  props.navigateToObjectVersions({
                    typeCategory: 'dataset',
                    latest: true,
                  });
                },
              },
            ],
          },
          {
            title: 'Calls', // 'Traces (Calls)',
            selected:
              props.selectedCategory === 'calls' &&
              !(
                props.filterCategory === 'train' ||
                props.filterCategory === 'predict' ||
                props.filterCategory === 'score' ||
                props.filterCategory === 'evaluate' ||
                props.filterCategory === 'tune'
              ),
            icon: <Segment />,
            onClick: () => {
              props.navigateToCalls({
                traceRootsOnly: true,
              });
            },
            // TODO: Get Feedback from team on this
            children: [
              {
                title: 'Train',
                selected: props.filterCategory === 'train',
                icon: <ModelTraining />,
                onClick: () => {
                  props.navigateToCalls({opCategory: 'train'});
                },
              },
              {
                title: 'Predict',
                selected: props.filterCategory === 'predict',
                icon: <AutoFixHigh />,
                onClick: () => {
                  props.navigateToCalls({opCategory: 'predict'});
                },
              },
              {
                title: 'Score',
                selected: props.filterCategory === 'score',
                icon: <Scoreboard />,
                onClick: () => {
                  props.navigateToCalls({opCategory: 'score'});
                },
              },
              {
                title: 'Evaluate',
                selected: props.filterCategory === 'evaluate',
                icon: <Rule />,
                onClick: () => {
                  props.navigateToCalls({opCategory: 'evaluate'});
                },
              },
              {
                title: 'Tune',
                selected: props.filterCategory === 'tune',
                icon: <Tune />,
                onClick: () => {
                  props.navigateToCalls({opCategory: 'tune'});
                },
              },
            ],
          },
        ],
      },
      {
        title: 'Structure',
        items: [
          {
            title: 'Types', // 'Classes (TypeVersions)',
            selected: props.selectedCategory === 'types',
            icon: <TypeSpecimen />,
            onClick: () => {
              props.navigateToTypeVersions();
            },
          },
          {
            title: 'Operations', // 'Methods (OpDefVersions)',
            selected: props.selectedCategory === 'ops',
            icon: <ManageHistory />,
            onClick: () => {
              props.navigateToOpVersions({
                isLatest: true,
              });
            },
          },
        ],
      },
      {
        title: 'Analytics',
        items: [
          {
            title: 'Boards',
            selected: props.selectedCategory === 'boards',
            icon: <DashboardCustomize />,
            onClick: () => {
              props.navigateToBoards();
            },
          },
          {
            title: 'Tables',
            selected: props.selectedCategory === 'tables',
            icon: <TableChart />,
            onClick: () => {
              props.navigateToTables();
            },
          },
        ],
      },
    ];
  }, [props]);
  return sections;
};
