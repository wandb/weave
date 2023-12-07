// import {Box} from '@mui/material';
import React from 'react';

// import {Node} from '../../../../../core';
// import {CenterProjectTablesBrowser2} from '../../HomeCenterEntityBrowser';
import {UnderConstruction} from './common/UnderConstruction';

export const TablesPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return (
    <UnderConstruction
      title="Tables"
      message={
        <>This page will contain a listing of the Tables in the project</>
      }
    />
  );
  // const [previewNode, setPreviewNode] = React.useState<React.ReactNode>(null);
  // return (
  //   <Box
  //     style={{
  //       height: '100%',
  //       width: '100%',
  //       overflow: 'hidden',
  //       display: 'flex',
  //       flexDirection: 'row',
  //       flex: '1 1 auto',
  //     }}>
  //     <Box
  //       style={{
  //         height: '100%',
  //         width: '100%',
  //         overflow: 'hidden',
  //         display: 'flex',
  //         flexDirection: 'column',
  //         flex: '1 1 auto',
  //       }}>
  //       <CenterProjectTablesBrowser2
  //         entityName={props.entity}
  //         projectName={props.project}
  //         setPreviewNode={(
  //           node: React.ReactNode,
  //           requestedWidth?: string | undefined
  //         ) => {
  //           setPreviewNode(node);
  //           // throw new Error('Function not implemented.');
  //         }}
  //         navigateToExpression={(expression: Node) => {
  //           // throw new Error('Function not implemented.');
  //         }}
  //       />
  //     </Box>
  //     {previewNode}
  //   </Box>
  // );
};
