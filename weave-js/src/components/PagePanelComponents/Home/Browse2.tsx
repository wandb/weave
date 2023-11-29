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
import {RouteAwareBrowse2ProjectSideNav} from './Browse2/Browse2SideNav';
import {Browse2TracePage} from './Browse2/Browse2TracePage';
import {Browse2TracesPage} from './Browse2/Browse2TracesPage';
import {BoardsPage} from './Browse2/pages/BoardsPage';
import {Browse2Boards} from './Browse2/pages/Browse2Boards';
import {CallsPage} from './Browse2/pages/CallsPage';
import {ObjectVersionsPage} from './Browse2/pages/ObjectVersionsPage';
import {dummyImageURL, useQuery} from './Browse2/pages/util';

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
  const projectRootPagesPath =
    '/:entity/:project/:tab(types|type-versions|objects|object-versions|ops|op-versions|calls|boards|tables)';
  return (
    <Box sx={{display: 'flex', height: '100vh', overflow: 'auto'}}>
      <CssBaseline />
      <AppBar position="fixed" sx={{zIndex: theme => theme.zIndex.drawer + 1}}>
        <Toolbar>
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
      <Route path={`${projectRootPagesPath}?`}>
        <RouteAwareBrowse2ProjectSideNav />
      </Route>
      <Box component="main" sx={{flexGrow: 1, p: 3}}>
        <Toolbar />
        <Switch>
          <Route path={projectRootPagesPath}>
            <Browse2ProjectRoot />
          </Route>
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

const Browse2ProjectRoot: FC = () => {
  const params = useParams<Browse2Params>();
  const entity = params.entity ?? '';
  const project = params.project ?? '';
  const projectRoot = `:entity/:project`;
  return (
    <Switch>
      {/* TYPES */}
      <Route path={`/${projectRoot}/types/:typeName/versions/:digest?`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/types/:typeName`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/types`}>
        <Browse2Boards title={'Types'} />
      </Route>
      <Route path={`/${projectRoot}/type-versions`}>
        <Browse2Boards title={'Type Versions'} />
      </Route>
      {/* OBJECTS */}
      <Route path={`/${projectRoot}/objects/:objectName/versions/:digest?`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/objects/:objectName`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/objects`}>
        <Browse2Boards title={'Objects'} />
      </Route>
      <Route path={`/${projectRoot}/object-versions`}>
        <ObjectVersionsPage />
      </Route>
      {/* OPS */}
      <Route path={`/${projectRoot}/ops/:opName/versions/:digest?`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/ops/:opName`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/ops`}>
        <Browse2Boards title={'Ops'} />
      </Route>
      <Route path={`/${projectRoot}/op-versions`}>
        <Browse2Boards title={'Op Versions'} />
      </Route>
      {/* CALLS */}
      <Route path={`/${projectRoot}/calls/:callId`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/calls`}>
        <CallsPage />
      </Route>
      {/* BOARDS */}
      <Route path={`/${projectRoot}/boards/:boardId`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/boards`}>
        <BoardsPage entity={entity} project={project} />
      </Route>
      {/* TABLES */}
      <Route path={`/${projectRoot}/tables/:tableId`}>
        <Browse2DataModelRoute />
      </Route>
      <Route path={`/${projectRoot}/tables`}>
        <Browse2Boards title={'Tables'} />
      </Route>
    </Switch>
  );
};

interface Browse2DataModelRouteParams {
  entity?: string;
  project?: string;
  tab?: string;
}

const Browse2DataModelRoute: FC = props => {
  const params = useParams<Browse2DataModelRouteParams>();
  const search = useQuery();
  console.log('BROWSE2 DATA MODEL ROUTE', {params, search});

  return (
    <div
      style={{
        backgroundImage: `url(${dummyImageURL})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        width: '100%',
        height: '100%',
      }}
    />
  );
};
