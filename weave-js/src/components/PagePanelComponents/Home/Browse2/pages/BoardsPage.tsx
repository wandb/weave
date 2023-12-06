import {Box} from '@mui/material';
import React from 'react';

import {Node} from '../../../../../core';
import {CenterProjectBoardsBrowser2} from '../../HomeCenterEntityBrowser';

export const BoardsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const [previewNode, setPreviewNode] = React.useState<React.ReactNode>(null);
  return (
    <Box
      style={{
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'row',
        flex: '1 1 auto',
      }}>
      <Box
        style={{
          height: '100%',
          width: '100%',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          flex: '1 1 auto',
        }}>
        <CenterProjectBoardsBrowser2
          entityName={props.entity}
          projectName={props.project}
          setPreviewNode={(
            node: React.ReactNode,
            requestedWidth?: string | undefined
          ) => {
            setPreviewNode(node);
            // throw new Error('Function not implemented.');
          }}
          navigateToExpression={(expression: Node) => {
            // throw new Error('Function not implemented.');
          }}
        />
      </Box>
      {previewNode}
    </Box>
  );
};
