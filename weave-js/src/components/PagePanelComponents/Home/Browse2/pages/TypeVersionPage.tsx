import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';
import {Box, Tab, Tabs, Divider} from '@mui/material';

export const TypeVersionPage: React.FC = () => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          // pt: 3,
          pb: 0,
          pl: 3,
          pr: 3,
          height: 65, // manual to match sidebar
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
        }}>
        <Box
          sx={{
            pb: 2.5,
            // fontSize: '1.5rem',
            fontWeight: 600,
            fontSize: '1.5rem',
          }}>
          TypeVersion Page
        </Box>
        <Tabs value={0}>
          <Tab label="Overview" />
          <Tab label="Properties" />
          <Tab label="Hierarchy" />
        </Tabs>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}></Box>
    </Box>
  );
};

// {/* <div>
//       <h1>TypeVersionPage Placeholder</h1>
//       <div>
//         This is the detail page for TypeVersion. A TypeVersion is a "version" of
//         a weave "type". In the user's mind it is analogous to a specific
//         implementation of a python class.
//       </div>
//       <div>Migration Notes:</div>
//       <ul>
//         <li>THIS IS COMPLETELY MISSING IN WEAVEFLOW</li>
//       </ul>
//       <div>Primary Features:</div>
//       <ul>
//         <li>
//           Property Types - with links to child type pages if they are other
//           objects
//         </li>
//         <li>A type Hierarchy (with links to each parent type)</li>
//         <li>(future) Type/OpDef DAG Visual</li>
//       </ul>
//       <div>Links:</div>
//       <ul>
//         <li>
//           Link to parent Type ({' '}
//           <Link to={prefix('/types/type_name')}>/types/[type_name]</Link>)
//         </li>
//         <li>
//           Connection to all child ObjectVersions instances ({' '}
//           <Link
//             to={prefix(
//               '/object-versions?filter=instance_of=type_name:version'
//             )}>
//             /object-versions?filter=instance_of=type_name:version
//           </Link>
//           )
//         </li>
//         <li>
//           Connection to all child TypeVersions ({' '}
//           <Link
//             to={prefix(
//               '/type-versions?filter=descendant_of=type_name:version,alias=latest'
//             )}>
//             /type-versions?filter=descendant_of=type_name:version,alias=latest
//           </Link>
//           )
//         </li>
//         <li>
//           Connection to all consuming OpVersions ({' '}
//           <Link
//             to={prefix(
//               '/op-versions?filter=consumes=type_name:version,alias=latest'
//             )}>
//             /op-versions?filter=consumes=type_name:version,alias=latest
//           </Link>
//           )
//         </li>
//         <li>
//           Connection to all producing OpVersions ({' '}
//           <Link
//             to={prefix(
//               '/op-versions?filter=produces=type_name:version,alias=latest'
//             )}>
//             /op-versions?filter=produces=type_name:version,alias=latest
//           </Link>
//           )
//         </li>
//       </ul>
//     </div> */}
