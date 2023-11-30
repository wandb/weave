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

const drawerWidth = 240;

type NavigationCallbacks = {
  navigateToProject: (project: string) => void;
  navigateToObjectVersions: (filter?: string) => void;
  navigateToCalls: (filter?: string) => void;
  navigateToTypeVersions: (filter?: string) => void;
  navigateToOpVersions: (filter?: string) => void;
  navigateToBoards: (filter?: string) => void;
  navigateToTables: (filter?: string) => void;
};

type Browse2ProjectSideNavProps = {
  entity: string;
  project: string;
  selectedCategory?:
    | 'objects'
    | 'calls'
    | 'types'
    | 'ops'
    | 'boards'
    | 'tables';
} & NavigationCallbacks;

export const RouteAwareBrowse2ProjectSideNav: FC = props => {
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
  const selectedCategory = useMemo(() => {
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
  if (!currentProject || !currentEntity) {
    return null;
  }
  return (
    <Browse2ProjectSideNav
      entity={currentEntity}
      project={currentProject}
      selectedCategory={selectedCategory}
      navigateToProject={project => {
        history.push(`/${params.entity}/${project}`);
      }}
      navigateToObjectVersions={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/object-versions${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToCalls={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/calls${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToTypeVersions={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/type-versions${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToOpVersions={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/op-versions${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToBoards={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/boards${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToTables={(filter?: string) => {
        history.push(
          `/${params.entity}/${params.project}/tables${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
    />
  );
};

export const Browse2ProjectSideNav: FC<Browse2ProjectSideNavProps> = props => {
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
      <Box sx={{p: 2}}>
        <FormControl fullWidth>
          <Autocomplete
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
        <List component="div" disablePadding>
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
            <ListSubheader component="div" id="nested-list-subheader">
              <Divider />
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
      <Divider />
    </Box>
  );
};

const useSectionsForProject = (props: Browse2ProjectSideNavProps) => {
  // TODO: Lookup pinned sidebar items from entity/project + user
  const sections: SectionType[] = useMemo(() => {
    return [
      {
        title: 'Records',
        items: [
          {
            title: 'Objects', // , 'Instances (ObjectVersions)',
            selected: props.selectedCategory === 'objects',
            icon: <Category />,
            onClick: () => {
              props.navigateToObjectVersions();
            },
            children: [
              {
                title: 'Models',
                icon: <Layers />,
                onClick: () => {
                  props.navigateToObjectVersions('kind="model"');
                },
              },
              {
                title: 'Datasets',
                icon: <Dataset />,
                onClick: () => {
                  props.navigateToObjectVersions('kind="dataset"');
                },
              },
            ],
          },
          {
            title: 'Traces', // 'Traces (Calls)',
            selected: props.selectedCategory === 'calls',
            icon: <Segment />,
            onClick: () => {
              props.navigateToCalls('parent_id=null');
            },
            children: [
              {
                title: 'Train',
                icon: <ModelTraining />,
                onClick: () => {
                  props.navigateToCalls('kind="train"');
                },
              },
              {
                title: 'Predict',
                icon: <AutoFixHigh />,
                onClick: () => {
                  props.navigateToCalls('kind="predict"');
                },
              },
              {
                title: 'Score',
                icon: <Scoreboard />,
                onClick: () => {
                  props.navigateToCalls('kind="score"');
                },
              },
              {
                title: 'Evaluate',
                icon: <Rule />,
                onClick: () => {
                  props.navigateToCalls('kind="evaluate"');
                },
              },
              {
                title: 'Tune',
                icon: <Tune />,
                onClick: () => {
                  props.navigateToCalls('kind="tune"');
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
              props.navigateToTypeVersions('alias="latest"');
            },
          },
          {
            title: 'Operations', // 'Methods (OpDefVersions)',
            selected: props.selectedCategory === 'ops',
            icon: <ManageHistory />,
            onClick: () => {
              props.navigateToOpVersions('alias="latest"');
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
