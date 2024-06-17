import {
  Category,
  ManageHistory,
  NavigateBefore,
  NavigateNext,
  Segment,
  Undo,
} from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  FormControl,
  IconButton,
  ListSubheader,
  TextField,
} from '@mui/material';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import React, {
  FC,
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useHistory, useParams} from 'react-router-dom';

import {useProjectsForEntity} from '../query';
import {useWeaveflowRouteContext} from './context';
import {WFHighLevelCallFilter} from './pages/CallsPage/callsTableFilter';
import {WFHighLevelObjectVersionFilter} from './pages/ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from './pages/OpVersionsPage';
import {useURLSearchParamsDict} from './pages/util';

const drawerWidth = 240;

type NavigationCallbacks = {
  navigateToProject: (project: string) => void;
  navigateToObjectVersions: (filter?: WFHighLevelObjectVersionFilter) => void;
  navigateToCalls: (filter?: WFHighLevelCallFilter) => void;
  navigateToOpVersions: (filter?: WFHighLevelOpVersionFilter) => void;
  navigateToBoards: () => void;
  navigateToTables: () => void;
  navigateAwayFromProject?: () => void;
};

type Browse3ProjectSideNavProps = {
  entity: string;
  project: string;
  /**
   * If true, the sidebar will be collapsed by default.
   * If false, the sidebar will be expanded by default.
   * If undefined, the sidebar will be expanded by default unless there is a peekPath.
   */
  preferCollapsed?: boolean;
  selectedCategory?:
    | 'objects'
    | 'calls'
    | 'types'
    | 'ops'
    | 'boards'
    | 'tables';
  filterCategory?: string;
} & NavigationCallbacks;

export const RouteAwareBrowse3ProjectSideNav: FC<{
  navigateAwayFromProject?: () => void;
}> = props => {
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
  const containsPeekPath = useMemo(() => {
    return query.peekPath != null && query.peekPath !== '';
  }, [query.peekPath]);
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

  const {baseRouter} = useWeaveflowRouteContext();
  if (!currentProject || !currentEntity) {
    return null;
  }
  return (
    <Browse3ProjectSideNav
      entity={currentEntity}
      project={currentProject}
      selectedCategory={selectedNavSection}
      filterCategory={filterCategory}
      preferCollapsed={containsPeekPath}
      navigateToProject={project => {
        history.push(baseRouter.projectUrl(params.entity, project));
      }}
      navigateToObjectVersions={(filter?: WFHighLevelObjectVersionFilter) => {
        history.push(
          baseRouter.objectVersionsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToCalls={(filter?: WFHighLevelCallFilter) => {
        history.push(
          baseRouter.callsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToOpVersions={(filter?: WFHighLevelOpVersionFilter) => {
        history.push(
          baseRouter.opVersionsUIUrl(params.entity, params.project, filter)
        );
      }}
      navigateToBoards={() => {
        history.push(baseRouter.boardsUIUrl(params.entity, params.project));
      }}
      navigateToTables={() => {
        history.push(baseRouter.tablesUIUrl(params.entity, params.project));
      }}
      navigateAwayFromProject={props.navigateAwayFromProject}
    />
  );
};

const Browse3ProjectSideNav: FC<Browse3ProjectSideNavProps> = props => {
  const sections = useSectionsForProject(props);
  const entityProjectsValue = useProjectsForEntity(props.entity);
  const projects = useMemo(() => {
    return [props.project, ...(entityProjectsValue.result ?? [])];
  }, [entityProjectsValue.result, props.project]);
  const wbSidebarWidth = 57;
  const wbSideBarSpeed = 0.2;
  const initialWidth = drawerWidth - wbSidebarWidth;
  const [userControlledOpen, setUserControlledOpen] = useState<
    boolean | undefined
  >(undefined);
  const open = useMemo(() => {
    if (userControlledOpen !== undefined) {
      return userControlledOpen;
    }
    return !props.preferCollapsed;
  }, [props.preferCollapsed, userControlledOpen]);
  const adjustedDrawerWidth = useMemo(() => {
    return open ? drawerWidth : wbSidebarWidth;
  }, [open]);
  const [width, setWidth] = useState(initialWidth);
  const onNavigateAwayFromProject = useCallback(() => {
    if (!props.navigateAwayFromProject) {
      return;
    }
    setWidth(0);
    setTimeout(() => {
      props.navigateAwayFromProject!();
    }, wbSideBarSpeed * 1000);
  }, [props.navigateAwayFromProject]);
  useEffect(() => {
    const t = setTimeout(() => {
      setWidth(adjustedDrawerWidth);
    }, 0);
    return () => clearTimeout(t);
  }, [adjustedDrawerWidth]);

  return (
    <Drawer
      variant="permanent"
      sx={{
        '&>div.MuiPaper-root': {
          position: 'relative',
          zIndex: 900,
        },
        flex: '0 0 auto',
        width,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width,
          boxSizing: 'border-box',
          transition: `width ${wbSideBarSpeed}s linear`,
        },
        transition: `width ${wbSideBarSpeed}s linear`,
      }}>
      <Box
        sx={{
          pl: 1,
          pr: 1,
          pt: 2,
          pb: 2,
          height: 55, // manual to match sidebar
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-evenly',
          flexDirection: 'row',
          gap: 1,
        }}>
        <IconButton size="small" onClick={() => setUserControlledOpen(o => !o)}>
          {open ? <NavigateBefore /> : <NavigateNext />}
        </IconButton>
        {open && (
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
        )}
      </Box>

      <SideNav sections={sections} open={open} />

      {props.navigateAwayFromProject && (
        <Box
          sx={{
            height: 52,
            borderTop: '1px solid #e0e0e0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexDirection: 'row',
            // gap: 1,
            flex: '0 0 auto',
            overflow: 'hidden',
          }}>
          <ListItemButton
            sx={{height: '100%', width: '100%'}}
            onClick={() => {
              onNavigateAwayFromProject();
            }}>
            <ListItemIcon>
              <Undo />
            </ListItemIcon>
            <ListItemText
              sx={{
                '&>span.MuiTypography-root': {
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                  whiteSpace: 'nowrap',
                },
              }}
              primary="Back to Experiments"
            />
          </ListItemButton>
        </Box>
      )}
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
const SideBarNavItem: FC<{
  item: ItemType;
  depth?: number;
  open: boolean;
}> = props => {
  const depth = props.depth ?? 0;
  const show = props.open || depth === 0;
  return (
    <Fragment>
      <ListItemButton
        sx={{
          pl: 2 + depth,
          height: !show ? 0 : 48,
          opacity: !show ? 0 : undefined,
          pt: !show ? 0 : undefined,
          pb: !show ? 0 : undefined,
          overflow: 'hidden',
          transition: 'all 0.3s ease-in-out',
        }}
        onClick={props.item.onClick}
        selected={props.item.selected}>
        <ListItemIcon>{props.item.icon}</ListItemIcon>
        <ListItemText primary={props.item.title} />
      </ListItemButton>
      {props.item.children && (
        <List disablePadding>
          {props.item.children.map((item, itemIndex) => {
            return (
              <SideBarNavItem
                item={item}
                depth={depth + 2}
                key={itemIndex}
                open={props.open}
              />
            );
          })}
        </List>
      )}
    </Fragment>
  );
};
const SideNav: FC<{
  open: boolean;
  sections: SectionType[];
}> = props => {
  return (
    <Box sx={{overflow: 'auto', flex: '1 1 auto'}}>
      {props.sections.map((section, sectionIndex) => {
        return (
          <Fragment key={sectionIndex}>
            <ListSubheader
              id="nested-list-subheader"
              sx={{
                pt: !props.open ? 0 : 1,
                height: !props.open ? 0 : 48,
                opacity: !props.open ? 0 : undefined,
                overflow: 'hidden',
                transition: 'all 0.3s ease-in-out',
              }}>
              {/* {sectionIndex !== 0 && <Divider />} */}
              {section.title}
              <Divider />
            </ListSubheader>
            <List
              sx={{
                p: !props.open ? 0 : undefined,
                transition: 'all 0.3s ease-in-out',
              }}>
              {section.items.map((item, itemIndex) => {
                return (
                  <SideBarNavItem
                    item={item}
                    key={itemIndex}
                    open={props.open}
                  />
                );
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
        title: 'Structure',
        items: [
          {
            title: 'Operations', // 'Methods (OpDefVersions)',
            selected: props.selectedCategory === 'ops',
            icon: <ManageHistory />,
            onClick: () => {
              props.navigateToOpVersions({});
            },
          },
        ],
      },
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
              props.navigateToObjectVersions({});
            },
            // TODO: Get Feedback from team on this
            // children: [
            //   {
            //     title: 'Models',
            //     icon: <Layers />,
            //     selected: props.filterCategory === 'model',
            //     onClick: () => {
            //       props.navigateToObjectVersions({
            //         typeCategory: 'model',
            //         latest: true,
            //       });
            //     },
            //   },
            //   {
            //     title: 'Datasets',
            //     icon: <Dataset />,
            //     selected: props.filterCategory === 'dataset',
            //     onClick: () => {
            //       props.navigateToObjectVersions({
            //         typeCategory: 'dataset',
            //         latest: true,
            //       });
            //     },
            //   },
            // ],
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
            // children: [
            //   {
            //     title: 'Train',
            //     selected: props.filterCategory === 'train',
            //     icon: <ModelTraining />,
            //     onClick: () => {
            //       props.navigateToCalls({opCategory: 'train'});
            //     },
            //   },
            //   {
            //     title: 'Predict',
            //     selected: props.filterCategory === 'predict',
            //     icon: <AutoFixHigh />,
            //     onClick: () => {
            //       props.navigateToCalls({opCategory: 'predict'});
            //     },
            //   },
            //   {
            //     title: 'Score',
            //     selected: props.filterCategory === 'score',
            //     icon: <Scoreboard />,
            //     onClick: () => {
            //       props.navigateToCalls({opCategory: 'score'});
            //     },
            //   },
            //   {
            //     title: 'Evaluate',
            //     selected: props.filterCategory === 'evaluate',
            //     icon: <Rule />,
            //     onClick: () => {
            //       props.navigateToCalls({opCategory: 'evaluate'});
            //     },
            //   },
            //   {
            //     title: 'Tune',
            //     selected: props.filterCategory === 'tune',
            //     icon: <Tune />,
            //     onClick: () => {
            //       props.navigateToCalls({opCategory: 'tune'});
            //     },
            //   },
            // ],
          },
        ],
      },
      // {
      //   title: 'Structure',
      //   items: [
      //     {
      //       title: 'Types', // 'Classes (TypeVersions)',
      //       selected: props.selectedCategory === 'types',
      //       icon: <TypeSpecimen />,
      //       onClick: () => {
      //         props.navigateToTypeVersions();
      //       },
      //     },
      //     {
      //       title: 'Operations', // 'Methods (OpDefVersions)',
      //       selected: props.selectedCategory === 'ops',
      //       icon: <ManageHistory />,
      //       onClick: () => {
      //         props.navigateToOpVersions({
      //           isLatest: true,
      //         });
      //       },
      //     },
      //   ],
      // },
      // {
      //   title: 'Analytics',
      //   items: [
      //     {
      //       title: 'Boards',
      //       selected: props.selectedCategory === 'boards',
      //       icon: <DashboardCustomize />,
      //       onClick: () => {
      //         props.navigateToBoards();
      //       },
      //     },
      //     {
      //       title: 'Tables',
      //       selected: props.selectedCategory === 'tables',
      //       icon: <TableChart />,
      //       onClick: () => {
      //         props.navigateToTables();
      //       },
      //     },
      //   ],
      // },
    ];
  }, [props]);
  return sections;
};
