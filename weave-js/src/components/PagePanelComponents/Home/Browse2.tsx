import React, {FC} from 'react';
import {Switch, Route, Link as RouterLink, useParams} from 'react-router-dom';

import {URL_BROWSE2} from '../../../urls';

import {
  AppBar,
  IconButton,
  Link as MaterialLink,
  Toolbar,
  Typography,
  Breadcrumbs,
  Box,
  Container,
} from '@mui/material';
import {Home} from '@mui/icons-material';
import {LicenseInfo} from '@mui/x-license-pro';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2ProjectPage} from './Browse2/Browse2ProjectPage';
import {Browse2ObjectTypePage} from './Browse2/Browse2ObjectTypePage';
import {Browse2ObjectVersionItemPage} from './Browse2/Browse2ObjectVersionItemPage';
import {Browse2ObjectPage} from './Browse2/Browse2ObjectPage';
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
          <Typography>row</Typography>
        ) : field === 'pick' ? (
          <Typography>col</Typography>
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

export const Browse2: FC = props => {
  return (
    <div
      style={{
        height: '100vh',
        overflow: 'auto',
        backgroundColor: '#fafafa',
      }}>
      <AppBar position="static">
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
      <Container maxWidth="xl">
        <Box sx={{height: 40}} />
        <Switch>
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
      </Container>
    </div>
  );
};
