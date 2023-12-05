import React from 'react';

import {SimplePageLayout} from '../SimplePageLayout';

export const TypeVersionPage: React.FC<{
  entity: string;
  project: string;
  typeName: string;
  version: string;
}> = () => {
  return (
    <SimplePageLayout
      title="TypeVersion Page"
      tabs={[
        {
          label: 'Overview',
          content: <div>Overview</div>,
        },
        {
          label: 'Properties',
          content: <div>Properties</div>,
        },
        {
          label: 'Hierarchy',
          content: <div>Hierarchy</div>,
        },
      ]}
    />
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
