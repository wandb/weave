import {Link as MaterialLink, Paper as MaterialPaper} from '@mui/material';
import {Box, Typography} from '@mui/material';
import * as globals from '@wandb/weave/common/css/globals.styles';
import React, {FC} from 'react';
import {Link as RouterLink, useLocation} from 'react-router-dom';
import styled from 'styled-components';

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

export interface Browse2RootObjectVersionItemParams {
  entity: string;
  project: string;
  rootType: string;
  objName: string;
  objVersion: string;
  refExtra?: string;
}
export function useQuery() {
  const {search} = useLocation();

  return React.useMemo(() => new URLSearchParams(search), [search]);
}
const escapeAndRenderControlChars = (str: string) => {
  const controlCharMap: {[key: string]: string | undefined} = {
    '\n': '\\n',
    '\t': '\\t',
    '\r': '\\r',
  };

  return str.split('').map((char, index) => {
    if (controlCharMap[char]) {
      return (
        <span key={index}>
          <span style={{color: globals.MOON_400}}>{controlCharMap[char]}</span>
          {char === '\n' ? (
            <br />
          ) : (
            <span style={{width: '2em', display: 'inline-block'}}></span>
          )}
        </span>
      );
    }
    return char;
  });
};
export const DisplayControlChars = ({text}: {text: string}) => {
  return <Typography>{escapeAndRenderControlChars(text)}</Typography>;
};
