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
import CssBaseline from '@mui/material/CssBaseline';
import {LicenseInfo} from '@mui/x-license-pro';
import React, {FC} from 'react';
import {
  Link as RouterLink,
  Route,
  Switch,
  useHistory,
  useParams,
  useLocation,
} from 'react-router-dom';

import {URL_BROWSE2} from '../../../urls';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {Browse2ObjectPage} from './Browse2/Browse2ObjectPage';
import {Browse2ObjectTypePage} from './Browse2/Browse2ObjectTypePage';
import {Browse2ObjectVersionItemPage} from './Browse2/Browse2ObjectVersionItemPage';
import {Browse2ProjectPage} from './Browse2/Browse2ProjectPage';
import {Browse2TracePage} from './Browse2/Browse2TracePage';
import {Browse2TracesPage} from './Browse2/Browse2TracesPage';
import {Browse2ProjectSideNav} from './Browse2SideNav';
import _ from 'lodash';

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
        <AppBarLink to={`/${URL_BROWSE2}/${params.entity}`}>
          {params.entity}
        </AppBarLink>
      )}
      {params.project && (
        <AppBarLink to={`/${URL_BROWSE2}/${params.entity}/${params.project}`}>
          {params.project}
        </AppBarLink>
      )}
      {params.rootType && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}`}>
          {params.rootType}
        </AppBarLink>
      )}
      {params.objName && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}`}>
          {params.objName}
        </AppBarLink>
      )}
      {params.objVersion && (
        <AppBarLink
          to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${params.rootType}/${params.objName}/${params.objVersion}`}>
          {params.objVersion}
        </AppBarLink>
      )}
      {refFields.map((field, idx) =>
        field === 'index' ? (
          <Typography
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            row
          </Typography>
        ) : field === 'pick' ? (
          <Typography
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            col
          </Typography>
        ) : (
          <AppBarLink
            to={`/${URL_BROWSE2}/${params.entity}/${params.project}/${
              params.rootType
            }/${params.objName}/${params.objVersion}/${refFields
              .slice(0, idx + 1)
              .join('/')}`}>
            {field}
          </AppBarLink>
        )
      )}
    </Breadcrumbs>
  );
};

const RouteAwareBrowse2ProjectSideNav: FC = props => {
  const params = useParams<Browse2Params>();
  const history = useHistory();
  const currentProject = params.project;
  const currentEntity = params.entity;
  if (!currentProject || !currentEntity) {
    return null;
  }
  return (
    <Browse2ProjectSideNav
      entity={currentEntity}
      project={currentProject}
      navigateToProject={project => {
        history.push(`/${URL_BROWSE2}/${params.entity}/${project}`);
      }}
      navigateToObjects={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/objects${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToCalls={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/calls${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToTypes={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/types${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToOps={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/ops${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToBoards={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/boards${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
      navigateToTables={(filter?: string) => {
        history.push(
          `/${URL_BROWSE2}/${params.entity}/${params.project}/tables${
            filter ? `?filter=${filter}` : ''
          }`
        );
      }}
    />
  );
};

export const Browse2: FC = props => {
  const projectRoot = `${URL_BROWSE2}/:entity/:project`;
  return (
    <Box sx={{display: 'flex', height: '100vh', overflow: 'auto'}}>
      <CssBaseline />
      <AppBar position="fixed" sx={{zIndex: theme => theme.zIndex.drawer + 1}}>
        <Toolbar>
          <IconButton
            component={RouterLink}
            to={`/${URL_BROWSE2}`}
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
          <Browse2Breadcrumbs />
        </Toolbar>
      </AppBar>
      <Route path={`/${URL_BROWSE2}/:entity/:project`}>
        <RouteAwareBrowse2ProjectSideNav />
      </Route>
      <Box component="main" sx={{flexGrow: 1, p: 3}}>
        <Toolbar />
        <Switch>
          {/* TIM's ADDITIONS */}
          {/* TYPES */}
          <Route path={`/${projectRoot}/types/:typeName/versions/:digest?`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/types/:typeName`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/types`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/type-versions`}>
            <Browse2DataModelRoute />
          </Route>
          {/* OBJECTS */}
          <Route path={`/${projectRoot}/objects/:objectName/versions/:digest?`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/objects/:objectName`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/objects`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/object-versions`}>
            <Browse2DataModelRoute />
          </Route>
          {/* OPS */}
          <Route path={`/${projectRoot}/ops/:opName/versions/:digest?`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/ops/:opName`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/ops`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/op-versions`}>
            <Browse2DataModelRoute />
          </Route>
          {/* CALLS */}
          <Route path={`/${projectRoot}/calls/:callId`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/calls`}>
            <Browse2DataModelRoute />
          </Route>
          {/* BOARDS */}
          <Route path={`/${projectRoot}/boards/:boardId`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/boards`}>
            <Browse2DataModelRoute />
          </Route>
          {/* TABLES */}
          <Route path={`/${projectRoot}/tables/:tableId`}>
            <Browse2DataModelRoute />
          </Route>
          <Route path={`/${projectRoot}/tables`}>
            <Browse2DataModelRoute />
          </Route>
          {/* END TIM's ADDITIONS */}
          <Route
            path={`/${URL_BROWSE2}/:entity/:project/trace/:traceId/:spanId?`}>
            <Browse2TracePage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/trace`}>
            <Browse2TracesPage />
          </Route>
          <Route
            path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName/:objVersion/:refExtra*`}>
            <Browse2ObjectVersionItemPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType/:objName`}>
            <Browse2ObjectPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project/:rootType`}>
            <Browse2ObjectTypePage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity/:project`}>
            <Browse2ProjectPage />
          </Route>
          <Route path={`/${URL_BROWSE2}/:entity`}>
            <Browse2EntityPage />
          </Route>
          <Route path={`/${URL_BROWSE2}`}>
            <Browse2HomePage />
          </Route>
        </Switch>
      </Box>
    </Box>
  );
};

interface Browse2DataModelRouteParams {
  entity?: string;
  project?: string;
  tab?: string;
}

function useQuery() {
  const {search} = useLocation();

  return React.useMemo(() => {
    const params = new URLSearchParams(search);
    const entries = Array.from(params.entries());
    const searchDict = _.fromPairs(entries);
    return searchDict;
  }, [search]);
}

const Browse2DataModelRoute: FC = props => {
  const params = useParams<Browse2DataModelRouteParams>();
  const search = useQuery();
  return <pre>{JSON.stringify({params, search}, null, 2)}</pre>;
};
