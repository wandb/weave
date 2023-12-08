import {Home} from '@mui/icons-material';
import {
  AppBar,
  Box,
  Breadcrumbs,
  IconButton,
  Link as MaterialLink,
  Toolbar,
  Typography,
} from '@mui/material';
import {LicenseInfo} from '@mui/x-license-pro';
import React, {FC} from 'react';
import {
  BrowserRouter as Router,
  Link as RouterLink,
  Route,
  Switch,
  useParams,
} from 'react-router-dom';

import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {Browse2ObjectPage} from './Browse2/Browse2ObjectPage';
import {Browse2ObjectTypePage} from './Browse2/Browse2ObjectTypePage';
import {Browse2ObjectVersionItemPage} from './Browse2/Browse2ObjectVersionItemPage';
import {Browse2ProjectPage} from './Browse2/Browse2ProjectPage';
import {Browse2TracePage} from './Browse2/Browse2TracePage';
import {Browse2TracesPage} from './Browse2/Browse2TracesPage';
LicenseInfo.setLicenseKey(
  '7684ecd9a2d817a3af28ae2a8682895aTz03NjEwMSxFPTE3MjgxNjc2MzEwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLEtWPTI='
);

interface Browse2Params {
  entity?: string;
  project?: string;
  rootType?: string;
  objName?: string;
  objVersion?: string;
  refExtra?: string;
}

const AppBarLink = (props: React.ComponentProps<typeof RouterLink>) => (
  <MaterialLink
    sx={{
      color: theme => theme.palette.getContrastText(theme.palette.primary.main),
      '&:hover': {
        color: theme =>
          theme.palette.getContrastText(theme.palette.primary.dark),
      },
    }}
    {...props}
    component={RouterLink}
  />
);

const Browse2Breadcrumbs: FC = props => {
  const params = useParams<Browse2Params>();
  const refFields = params.refExtra?.split('/') ?? [];
  return (
    <Breadcrumbs>
      {params.entity && (
        <AppBarLink to={`/${params.entity}`}>{params.entity}</AppBarLink>
      )}
      {params.project && (
        <AppBarLink to={`/${params.entity}/${params.project}`}>
          {params.project}
        </AppBarLink>
      )}
      {params.rootType && (
        <AppBarLink
          to={`/${params.entity}/${params.project}/${params.rootType}`}>
          {params.rootType}
        </AppBarLink>
      )}
      {params.objName && (
        <AppBarLink
          to={`/${params.entity}/${params.project}/${params.rootType}/${params.objName}`}>
          {params.objName}
        </AppBarLink>
      )}
      {params.objVersion && (
        <AppBarLink
          to={`/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`}>
          {params.objVersion}
        </AppBarLink>
      )}
      {refFields.map((field, idx) =>
        field === 'index' ? (
          <Typography
            key={idx}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            row
          </Typography>
        ) : field === 'pick' ? (
          <Typography
            key={idx}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            col
          </Typography>
        ) : (
          <AppBarLink
            key={idx}
            to={`/${params.entity}/${params.project}/${params.rootType}/${
              params.objName
            }/${params.objVersion}/${refFields.slice(0, idx + 1).join('/')}`}>
            {field}
          </AppBarLink>
        )
      )}
    </Breadcrumbs>
  );
};

export const Browse2: FC<{basename: string}> = props => {
  return (
    <Router basename={props.basename}>
      <Browse2Mounted />
    </Router>
  );
};

const Browse2Mounted: FC = props => {
  return (
    <Box sx={{display: 'flex', height: '100vh', overflow: 'auto'}}>
      {/* <CssBaseline /> */}
      <AppBar
        position="fixed"
        sx={{
          zIndex: theme => theme.zIndex.drawer + 1,
          // height: '30px',
          // minHeight: '30px',
        }}>
        <Toolbar
          // variant="dense"
          sx={{
            backgroundColor: '#1976d2',
            // height: '30px',
            minHeight: '30px',
          }}>
          <IconButton
            component={RouterLink}
            to={`/`}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
              '&:hover': {
                color: theme =>
                  theme.palette.getContrastText(theme.palette.primary.dark),
              },
              marginRight: theme => theme.spacing(2),
            }}>
            <Home />
          </IconButton>
          <Route
            path={`/:entity?/:project?/:rootType?/:objName?/:objVersion?/:refExtra*`}>
            <Browse2Breadcrumbs />
          </Route>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{flexGrow: 1, p: 3}}>
        <Toolbar />
        <Switch>
          <Route path={`/:entity/:project/trace/:traceId/:spanId?`}>
            <Browse2TracePage />
          </Route>
          <Route path={`/:entity/:project/trace`}>
            <Browse2TracesPage />
          </Route>
          <Route
            path={`/:entity/:project/:rootType/:objName/:objVersion/:refExtra*`}>
            <Browse2ObjectVersionItemPage />
          </Route>
          <Route path={`/:entity/:project/:rootType/:objName`}>
            <Browse2ObjectPage />
          </Route>
          <Route path={`/:entity/:project/:rootType`}>
            <Browse2ObjectTypePage />
          </Route>
          <Route path={`/:entity/:project`}>
            <Browse2ProjectPage />
          </Route>
          <Route path={`/:entity`}>
            <Browse2EntityPage />
          </Route>
          <Route path={``}>
            <Browse2HomePage />
          </Route>
        </Switch>
      </Box>
    </Box>
  );
};
