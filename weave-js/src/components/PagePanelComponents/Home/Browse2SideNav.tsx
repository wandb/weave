import {
  AutoFixHigh,
  Category,
  DashboardCustomize,
  Dataset,
  Layers,
  ManageHistory,
  Rule,
  Scoreboard,
  Segment,
  TableChart,
  Train,
  Tune,
  TypeSpecimen,
} from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  FormControl,
  InputLabel,
  ListSubheader,
  MenuItem,
  Select,
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

export const Browse2ProjectSideNav: FC<{
  currentEntity: string;
  currentProject: string;
  onProjectChange: (project: string) => void;
}> = props => {
  const sections = useSectionsForProject(
    props.currentEntity,
    props.currentProject
  );
  const entityProjectsValue = useProjectsForEntity(props.currentEntity);
  const projects = useMemo(() => {
    return [props.currentProject, ...(entityProjectsValue.result ?? [])];
  }, [entityProjectsValue.result, props.currentProject]);
  // const projectOptions = useMemo(() => {
  //   return projects.map(project => {
  //     return {
  //       label: project,
  //       id: project,
  //     };
  //   });
  // }, [projects]);
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
            value={props.currentProject}
            onChange={(event, newValue) => {
              props.onProjectChange(newValue);
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
  children?: Array<ItemType>;
};
const SideBarNavItem: FC<{item: ItemType; depth?: number}> = props => {
  const depth = props.depth ?? 0;
  return (
    <Fragment>
      <ListItemButton sx={{pl: 2 + depth}}>
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

const useSectionsForProject = (entity: string, project: string) => {
  const sections: Array<SectionType> = useMemo(() => {
    return [
      {
        title: 'Records',
        items: [
          {
            title: 'Objects', //, 'Instances (ObjectVersions)',
            // An appropriate icon for "objects" from the MUI icon set is:
            icon: <Category />,
            children: [
              {
                title: 'Models',
                icon: <Layers />,
              },
              {
                title: 'Datasets',
                icon: <Dataset />,
              },
            ],
          },
          {
            title: 'Traces', // 'Traces (Calls)',
            icon: <Segment />,
            children: [
              {
                title: 'Train',
                icon: <Train />,
              },
              {
                title: 'Predict',
                icon: <AutoFixHigh />,
              },
              {
                title: 'Score',
                icon: <Scoreboard />,
              },
              {
                title: 'Evaluate',
                icon: <Rule />,
              },
              {
                title: 'Tune',
                icon: <Tune />,
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
          },
          {
            title: 'Operations', // 'Methods (OpDefVersions)',
            icon: <ManageHistory />,
          },
        ],
      },
      {
        title: 'Analytics',
        items: [
          {
            title: 'Boards',
            icon: <DashboardCustomize />,
          },
          {
            title: 'Tables',
            icon: <TableChart />,
          },
        ],
      },
    ];
  }, []);
  return sections;
};
