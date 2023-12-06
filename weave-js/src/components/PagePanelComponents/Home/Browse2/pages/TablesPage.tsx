import {Box} from '@mui/material';
import React from 'react';

import {Node} from '../../../../../core';
import {CenterProjectTablesBrowser2} from '../../HomeCenterEntityBrowser';

export const TablesPage: React.FC<{
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
        <CenterProjectTablesBrowser2
          entityName={props.entity}
          projectName={props.project}
          setPreviewNode={function (
            node: React.ReactNode,
            requestedWidth?: string | undefined
          ): void {
            setPreviewNode(node);
            // throw new Error('Function not implemented.');
          }}
          navigateToExpression={function (expression: Node): void {
            // throw new Error('Function not implemented.');
          }}
        />
      </Box>
      {previewNode}
    </Box>
  );
};
