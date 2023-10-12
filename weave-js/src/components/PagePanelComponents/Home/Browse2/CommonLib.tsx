import React, {FC} from 'react';

import {Link as RouterLink} from 'react-router-dom';
import {Paper as MaterialPaper, Link as MaterialLink} from '@mui/material';
import styled from 'styled-components';
import {Typography, Box} from '@mui/material';

export const Link = (props: React.ComponentProps<typeof RouterLink>) => (
  <MaterialLink {...props} component={RouterLink} />
);

export const Paper = (props: React.ComponentProps<typeof MaterialPaper>) => {
  return (
    <MaterialPaper
      sx={{
        padding: theme => theme.spacing(2),
      }}
      {...props}>
      {props.children}
    </MaterialPaper>
  );
};

export const PageEl = styled.div``;

export const PageHeader: FC<{
  objectType: string;
  objectName?: string;
  actions?: JSX.Element;
}> = ({objectType, objectName, actions}) => {
  return (
    <Box
      display="flex"
      alignItems="flex-start"
      justifyContent="space-between"
      mb={4}>
      <Box
        display="flex"
        alignItems="baseline"
        maxWidth={actions != null ? 800 : undefined}
        sx={{
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        marginRight={3}>
        <Typography variant="h4" component="span" style={{fontWeight: 'bold'}}>
          {objectType}
        </Typography>
        {objectName != null && (
          <Typography variant="h4" component="span" style={{marginLeft: '8px'}}>
            {objectName}
          </Typography>
        )}
      </Box>
      {actions}
    </Box>
  );
};
interface ObjPath {
  entity: string;
  project: string;
  objName: string;
  objVersion: string;
}
export const makeObjRefUri = (objPath: ObjPath) => {
  return `wandb-artifact:///${objPath.entity}/${objPath.project}/${objPath.objName}:${objPath.objVersion}/obj`;
};
