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
import {BoardPage} from './Browse2/pages/BoardPage';
import {BoardsPage} from './Browse2/pages/BoardsPage';
import {CallPage} from './Browse2/pages/CallPage';
import {CallsPage} from './Browse2/pages/CallsPage';
import {ObjectPage} from './Browse2/pages/ObjectPage';
import {ObjectsPage} from './Browse2/pages/ObjectsPage';
import {ObjectVersionPage} from './Browse2/pages/ObjectVersionPage';
import {ObjectVersionsPage} from './Browse2/pages/ObjectVersionsPage';
import {OpPage} from './Browse2/pages/OpPage';
import {OpsPage} from './Browse2/pages/OpsPage';
import {OpVersionPage} from './Browse2/pages/OpVersionPage';
import {OpVersionsPage} from './Browse2/pages/OpVersionsPage';
import {TablePage} from './Browse2/pages/TablePage';
import {TablesPage} from './Browse2/pages/TablesPage';
import {TypePage} from './Browse2/pages/TypePage';
import {TypesPage} from './Browse2/pages/TypesPage';
import {TypeVersionPage} from './Browse2/pages/TypeVersionPage';
import {TypeVersionsPage} from './Browse2/pages/TypeVersionsPage';

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
      <AppBar
        position="fixed"
        sx={{zIndex: theme => theme.zIndex.drawer + 1, height: '60px'}}>
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
      <Switch>
        <Route path={projectRootPagesPath}>
          <Box
            component="main"
            sx={{
              flexGrow: 1,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              pt: 3,
              pr: 3,
              pb: 0,
              pl: 3,
            }}>
            <Toolbar />
            <Browse2ProjectRoot />
          </Box>
        </Route>
        <Route>
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
        </Route>
      </Switch>
    </Box>
  );
};

const Browse2ProjectRoot: FC = () => {
  const projectRoot = `:entity/:project`;
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        overflow: 'auto',
      }}>
      <Switch>
        {/* TYPES */}
        <Route path={`/${projectRoot}/types/:typeName/versions/:digest?`}>
          <TypeVersionPage />
        </Route>
        <Route path={`/${projectRoot}/types/:typeName`}>
          <TypePage />
        </Route>
        <Route path={`/${projectRoot}/types`}>
          <TypesPage />
        </Route>
        <Route path={`/${projectRoot}/type-versions`}>
          <TypeVersionsPage />
        </Route>
        {/* OBJECTS */}
        <Route path={`/${projectRoot}/objects/:objectName/versions/:digest?`}>
          <ObjectVersionPage />
        </Route>
        <Route path={`/${projectRoot}/objects/:objectName`}>
          <ObjectPage />
        </Route>
        <Route path={`/${projectRoot}/objects`}>
          <ObjectsPage />
        </Route>
        <Route path={`/${projectRoot}/object-versions`}>
          <ObjectVersionsPage />
        </Route>
        {/* OPS */}
        <Route path={`/${projectRoot}/ops/:opName/versions/:digest?`}>
          <OpVersionPage />
        </Route>
        <Route path={`/${projectRoot}/ops/:opName`}>
          <OpPage />
        </Route>
        <Route path={`/${projectRoot}/ops`}>
          <OpsPage />
        </Route>
        <Route path={`/${projectRoot}/op-versions`}>
          <OpVersionsPage />
        </Route>
        {/* CALLS */}
        <Route path={`/${projectRoot}/calls/:callId`}>
          <CallPage />
        </Route>
        <Route path={`/${projectRoot}/calls`}>
          <CallsPage />
        </Route>
        {/* BOARDS */}
        <Route
          path={[
            `/${projectRoot}/boards/_new_board_`,
            `/${projectRoot}/boards/:boardId`,
            `/${projectRoot}/boards/:boardId/version/:versionId`,
          ]}>
          <BoardPage />
        </Route>
        <Route path={`/${projectRoot}/boards`}>
          <BoardsPage />
        </Route>
        {/* TABLES */}
        <Route path={`/${projectRoot}/tables/:tableId`}>
          <TablePage />
        </Route>
        <Route path={`/${projectRoot}/tables`}>
          <TablesPage />
        </Route>
      </Switch>
    </Box>
  );
};
