// import {Box, CssBaseline, Tab, Tabs, Typography} from '@material-ui/core';
import React, {useMemo} from 'react';

import {Browse2ObjectVersionItemComponent} from '../Browse2ObjectVersionItemPage';
import {Browse2RootObjectVersionItemParams} from '../CommonLib';
import {useObjectVersionTypeInfo} from './interface/dataModel';

// const MetadataTable = ({data}) => {
//   return (
//     // <Paper sx={{width: '100%', overflow: 'hidden'}}>
//     <Table size="small" aria-label="simple table">
//       {/* <TableHead>
//         <TableRow sx={{backgroundColor: '#f5f5f5'}}>
//           <TableCell>Key</TableCell>
//           <TableCell align="right">Value</TableCell>
//         </TableRow>
//       </TableHead> */}
//       <TableBody>
//         {Object.entries(data).map(([key, value]) => (
//           <TableRow key={key}>
//             <TableCell component="th" scope="row">
//               <strong>{key}</strong>
//             </TableCell>
//             <TableCell align="right">{value}</TableCell>
//           </TableRow>
//         ))}
//       </TableBody>
//     </Table>
//     // </Paper>
//   );
// };

// interface TabPanelProps {
//   children?: React.ReactNode;
//   index: number;
//   value: number;
// }

// function CustomTabPanel(props: TabPanelProps) {
//   const {children, value, index, ...other} = props;

//   return (
//     <div
//       role="tabpanel"
//       hidden={value !== index}
//       id={`simple-tabpanel-${index}`}
//       aria-labelledby={`simple-tab-${index}`}
//       {...other}>
//       {value === index && (
//         <Box sx={{p: 3}}>
//           <Typography>{children}</Typography>
//         </Box>
//       )}
//     </div>
//   );
// }

// function a11yProps(index: number) {
//   return {
//     id: `simple-tab-${index}`,
//     'aria-controls': `simple-tabpanel-${index}`,
//   };
// }

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  digest: string;
  refExtra?: string;
}> = props => {
  const objectVersionTypeInfo = useObjectVersionTypeInfo(
    props.entity,
    props.project,
    props.objectName,
    props.digest
  );
  const rootType = useMemo(() => {
    let targetType = objectVersionTypeInfo.result?.type_version;
    while (targetType?.parent_type) {
      targetType = targetType.parent_type;
    }
    return targetType;
  }, [objectVersionTypeInfo.result?.type_version]);
  const params: Browse2RootObjectVersionItemParams = useMemo(() => {
    return {
      entity: props.entity,
      project: props.project,
      rootType: rootType?.type_name ?? '',
      objName: props.objectName,
      objVersion: props.digest,
      refExtra: props.refExtra,
    };
  }, [
    props.digest,
    props.entity,
    props.objectName,
    props.project,
    props.refExtra,
    rootType?.type_name,
  ]);
  if (objectVersionTypeInfo.loading) {
    return <div>Loading...</div>;
  }
  return <Browse2ObjectVersionItemComponent params={params} />;
};

/*
<div>
      <h1>ObjectVersionPage Placeholder</h1>
      <div>
        This is the detail page for ObjectVersion. A ObjectVersion is a
        "version" of a saved weave object. In the user's mind it is analogous to
        a specific instance.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          Weaveflow pretty much already has this page (
          <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b">
            https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b
          </a>
          ) that includes most of what we will want here. However, this is one
          of the most important pages, so it is is worth enumerating the primary
          features
        </li>
      </ul>
      <div>Primary Features:</div>
      <ul>
        <li>Property Values (possibly editable)</li>
        <li>(future) Objet/Call DAG Visual</li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Link to parent TypeVersion ({' '}
          <Link to={prefix('/types/type_name/versions/version_id')}>
            /types/[type_name]/versions/[version_id]
          </Link>
          )
        </li>
        <li>
          Link to parent Object ({' '}
          <Link to={prefix('/objects/object_name')}>
            /objects/[object_name]
          </Link>
          )
        </li>
        <li>
          Link to Producing Call ({' '}
          <Link to={prefix('/calls/call_id')}>/calls/call_id</Link>)
        </li>
        <li>
          Link to all Consuming Calls ({' '}
          <Link to={prefix('/calls?filter=uses=object_version_id')}>
            /types/[type_name]/versions/[version_id]
          </Link>
          )
        </li>
      </ul>
      <div>Inspiration</div>
      Existing Weaveflow Page
      <br />
      <img
        src="https://github.com/wandb/weave/blob/a0d44639b972421890ed6149f9cbc01211749291/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/objectversion_example.png?raw=true"
        style={{
          width: '100%',
        }}
        alt=""
      />
    </div>
    */
