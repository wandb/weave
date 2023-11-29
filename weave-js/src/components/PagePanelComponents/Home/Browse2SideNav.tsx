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

import {useProjectsForEntity} from './query';

const drawerWidth = 240;

type NavigationCallbacks = {
  navigateToProject: (project: string) => void;
  navigateToObjects: (filter?: string) => void;
  navigateToCalls: (filter?: string) => void;
  navigateToTypes: (filter?: string) => void;
  navigateToOps: (filter?: string) => void;
  navigateToBoards: (filter?: string) => void;
  navigateToTables: (filter?: string) => void;
};

type Browse2ProjectSideNavProps = {
  entity: string;
  project: string;
} & NavigationCallbacks;

export const Browse2ProjectSideNav: FC<
  {
    entity: string;
    project: string;
  } & NavigationCallbacks
> = props => {
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
  items: Array<ItemType>;
};
type ItemType = {
  title: string;
  icon: React.ReactNode;
  onClick: () => void;
  children?: Array<ItemType>;
};
const SideBarNavItem: FC<{item: ItemType; depth?: number}> = props => {
  const depth = props.depth ?? 0;
  return (
    <Fragment>
      <ListItemButton sx={{pl: 2 + depth}} onClick={props.item.onClick}>
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
  sections: Array<SectionType>;
}> = props => {
  return (
    <Box sx={{overflow: 'auto'}}>
      {props.sections.map((section, sectionIndex) => {
        return (
          <Fragment key={sectionIndex}>
            <Divider />
            <ListSubheader component="div" id="nested-list-subheader">
              {section.title}
            </ListSubheader>
            <Divider />
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
  const sections: Array<SectionType> = useMemo(() => {
    return [
      {
        title: 'Records',
        items: [
          {
            title: 'Objects', //, 'Instances (ObjectVersions)',
            icon: <Category />,
            onClick: () => {
              props.navigateToObjects();
            },
            children: [
              {
                title: 'Models',
                icon: <Layers />,
                onClick: () => {
                  props.navigateToObjects('kind="model"');
                },
              },
              {
                title: 'Datasets',
                icon: <Dataset />,
                onClick: () => {
                  props.navigateToObjects('kind="dataset"');
                },
              },
            ],
          },
          {
            title: 'Traces', // 'Traces (Calls)',
            icon: <Segment />,
            onClick: () => {
              props.navigateToCalls();
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
            icon: <TypeSpecimen />,
            onClick: () => {
              props.navigateToTypes();
            },
          },
          {
            title: 'Operations', // 'Methods (OpDefVersions)',
            icon: <ManageHistory />,
            onClick: () => {
              props.navigateToOps();
            },
          },
        ],
      },
      {
        title: 'Analytics',
        items: [
          {
            title: 'Boards',
            icon: <DashboardCustomize />,
            onClick: () => {
              props.navigateToBoards();
            },
          },
          {
            title: 'Tables',
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
