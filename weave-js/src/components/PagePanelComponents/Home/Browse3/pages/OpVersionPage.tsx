import React from 'react';

import {Browse2OpDefCode} from '../../Browse2/Browse2OpDefCode';
import {CategoryChip} from './common/CategoryChip';
import {
  CallsLink,
  opNiceName,
  OpVersionLink,
  OpVersionsLink,
  opVersionText,
} from './common/Links';
import {CenteredAnimatedLoader} from './common/Loader';
import {
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from './common/SimplePageLayout';
import {UnderConstruction} from './common/UnderConstruction';
import {TabUseOp} from './TabUseOp';
import {useWeaveflowORMContext} from './wfInterface/context';
import {refDictToRefString} from './wfInterface/naive';
import {WFOpVersion} from './wfInterface/types';

export const OpVersionPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
  version: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const opVersion = orm.projectConnection.opVersion(
    refDictToRefString({
      entity: props.entity,
      project: props.project,
      artifactName: props.opName,
      versionCommitHash: props.version,
      filePathParts: ['obj'],
      refExtraTuples: [],
    })
  );
  if (opVersion == null) {
    return <CenteredAnimatedLoader />;
  }
  return <OpVersionPageInner opVersion={opVersion} />;
};

const OpVersionPageInner: React.FC<{
  opVersion: WFOpVersion;
}> = ({opVersion}) => {
  const uri = opVersion.refUri();
  const entity = opVersion.entity();
  const project = opVersion.project();
  const opName = opVersion.op().name();
  const opVersionCount = opVersion.op().opVersions().length;
  const opVersionCallCount = opVersion.calls().length;
  const opVersionIndex = opVersion.versionIndex();
  const opVersionCategory = opVersion.opCategory();
  const opInvokes = opVersion.invokes();

  return (
    <SimplePageLayoutWithHeader
      title={opVersionText(opName, opVersionIndex)}
      headerContent={
        <SimpleKeyValueTable
          data={{
            Name: (
              <>
                {opName} [
                <OpVersionsLink
                  entity={entity}
                  project={project}
                  filter={{
                    opName,
                  }}
                  versionCount={opVersionCount}
                  neverPeek
                  variant="secondary"
                />
                ]
              </>
            ),
            Version: <>{opVersionIndex}</>,
            Calls: (
              <CallsLink
                entity={entity}
                project={project}
                callCount={opVersionCallCount}
                filter={{
                  opVersionRefs: [opVersion.refUri()],
                }}
                neverPeek
                variant="secondary"
              />
            ),
            ...(opVersionCategory
              ? {
                  Category: <CategoryChip value={opVersionCategory} />,
                }
              : {}),

            // Dropping input types and output types for the time being since
            // we have de-prioritized type version navigation.
            // ...(opInputTypes.length > 0
            //   ? {
            //       'Input Types': (
            //         <ul style={{margin: 0}}>
            //           {opInputTypes.map((t, i) => (
            //             <li key={i}>
            //               <TypeVersionLink
            //                 entityName={t.entity()}
            //                 projectName={t.project()}
            //                 typeName={t.type().name()}
            //                 version={t.version()}
            //               />
            //             </li>
            //           ))}
            //         </ul>
            //       ),
            //     }
            //   : {}),
            // ...(opOutputTypes.length > 0
            //   ? {
            //       'Output Types': (
            //         <ul style={{margin: 0}}>
            //           {opOutputTypes.map((t, i) => (
            //             <li key={i}>
            //               <TypeVersionLink
            //                 entityName={t.entity()}
            //                 projectName={t.project()}
            //                 typeName={t.type().name()}
            //                 version={t.version()}
            //               />
            //             </li>
            //           ))}
            //         </ul>
            //       ),
            //     }
            //   : {}),
            ...(opInvokes.length > 0
              ? {'Call Tree': <OpVersionOpTree opVersion={opVersion} />}
              : {}),
          }}
        />
      }
      tabs={[
        {
          label: 'Code',
          content: (
            // <Box
            //   sx={{
            //     height: '100%',
            //     width: '100%',
            //     flexGrow: 1,
            //     overflow: 'hidden',
            //     pt: 4,
            //   }}>
            <Browse2OpDefCode uri={uri} />
            // </Box>
          ),
        },
        {
          label: 'Use',
          content: <TabUseOp name={opNiceName(opName)} uri={uri} />,
        },
        // {
        //   label: 'Calls',
        //   content: (
        //     <CallsTable
        //       entity={entity}
        //       project={project}
        //       frozenFilter={{
        //         opVersions: [opName + ':' + opVersionHash],
        //         traceRootsOnly: false,
        //       }}
        //     />
        //   ),
        // },
        // {
        //   label: 'Metadata',
        //   content: (
        //     <ScrollableTabContent>
        //       <SimpleKeyValueTable
        //         data={{
        //           Name: (
        //             <OpLink
        //               entityName={opVersion.entity()}
        //               projectName={opVersion.project()}
        //               opName={opName}
        //             />
        //           ),
        //           Category: (
        //             <OpVersionCategoryChip
        //               opCategory={opVersion.opCategory()}
        //             />
        //           ),
        //           Version: opVersionHash,
        //           'Input Types': (
        //             <ul style={{margin: 0}}>
        //               {opVersion.inputTypesVersions().map((t, i) => (
        //                 <li key={i}>
        //                   <TypeVersionLink
        //                     entityName={t.entity()}
        //                     projectName={t.project()}
        //                     typeName={t.type().name()}
        //                     version={t.version()}
        //                   />
        //                 </li>
        //               ))}
        //             </ul>
        //           ),
        //           'Output Types': (
        //             <ul style={{margin: 0}}>
        //               {opVersion.outputTypeVersions().map((t, i) => (
        //                 <li key={i}>
        //                   <TypeVersionLink
        //                     entityName={t.entity()}
        //                     projectName={t.project()}
        //                     typeName={t.type().name()}
        //                     version={t.version()}
        //                   />
        //                 </li>
        //               ))}
        //             </ul>
        //           ),
        //           'Call Tree': <OpVersionOpTree opVersion={opVersion} />,
        //         }}
        //       />
        //     </ScrollableTabContent>
        //   ),
        // },
        // {
        //   label: 'Invokes',
        //   content: (
        //     <FilterableOpVersionsTable
        //       entity={opVersion.entity()}
        //       project={opVersion.project()}
        //       frozenFilter={{
        //         invokedByOpVersions: [
        //           opVersion.op().name() + ':' + opVersion.version(),
        //         ],
        //       }}
        //     />
        //   ),
        // },
        // {
        //   label: 'Invoked By',
        //   content: (
        //     <FilterableOpVersionsTable
        //       entity={opVersion.entity()}
        //       project={opVersion.project()}
        //       frozenFilter={{
        //         invokesOpVersions: [
        //           opVersion.op().name() + ':' + opVersion.version(),
        //         ],
        //       }}
        //     />
        //   ),
        // },
        {
          label: 'Execute',
          content: (
            // <ScrollableTabContent><OpVersionExecute streamId={streamId} uri={uri} /> </ScrollableTabContent>
            <UnderConstruction
              title="Execute"
              message={
                <>
                  This page will allow you to call this op version with specific
                  inputs.
                </>
              }
            />
          ),
        },

        {
          label: 'DAG',
          content: (
            <UnderConstruction
              title="Structure DAG"
              message={
                <>
                  This page will show a "Structure" DAG of Types and Ops
                  centered at this particular op version.
                </>
              }
            />
          ),
        },
      ]}
    />
  );
  // return ;
};

const OpVersionOpTree: React.FC<{opVersion: WFOpVersion}> = ({opVersion}) => {
  return (
    <ul
      style={{
        paddingInlineStart: '22px',
        margin: 0,
      }}>
      {opVersion.invokes().map((v, i) => {
        return (
          <li key={i}>
            <OpVersionLink
              entityName={v.entity()}
              projectName={v.project()}
              opName={v.op().name()}
              version={v.commitHash()}
              versionIndex={v.versionIndex()}
            />
            <OpVersionOpTree opVersion={v} />
          </li>
        );
      })}
    </ul>
  );
};

// const OpVersionExecute: React.FC<{
//   streamId: StreamId;
//   uri: string;
// }> = ({streamId, uri}) => {
//   const firstCall = useFirstCall(streamId, uri);
//   const opSignature = useOpSignature(streamId, uri);
//   return (
//     <Paper>
//       <Typography variant="h6" gutterBottom>
//         Call Op
//       </Typography>
//       <Box sx={{width: 400}}>
//         {opSignature.result != null &&
//           Object.keys(opSignature.result.inputTypes).map(k => (
//             <Box key={k} mb={2}>
//               <TextField
//                 label={k}
//                 fullWidth
//                 value={
//                   firstCall.result != null
//                     ? firstCall.result.inputs[k]
//                     : undefined
//                 }
//               />
//             </Box>
//           ))}
//       </Box>
//       <Box pt={1}>
//         <Button variant="outlined" sx={{backgroundColor: globals.lightYellow}}>
//           Execute
//         </Button>
//       </Box>
//     </Paper>
//   );
// };
