
import React, {useMemo, useState} from 'react';
import { Box, Typography } from '@mui/material';
import { ParsedCall, WeaveDocumentSchema } from './schemas';
import { ObjectViewerSection } from '../CallPage/ObjectViewerSection';
import { DropdownSection, DocumentDropdown } from './DropdownMenu';

// interface DocumentCardProps {
//   doc: WeaveDocumentSchema;
// }

// export const DocumentCard: React.FC<DocumentCardProps> = ({ doc }) => {
//   const metadata = useMemo(() => {
//     if (doc.metadata && typeof doc.metadata === 'object' && doc.content) {
//       return doc.metadata;
//     }
//     return null;
//   }, [doc]);
//
//   return (
//     <Box
//       border={1}
//       borderColor={"#DFE0E2"}
//       borderRadius={"8px"}
//       paddingTop={"12px"}
//       paddingLeft={"16px"}
//       paddingBottom={"12px"}
//     >
//       <Typography variant="body2" color="text.secondary">
//         {doc.content}
//       </Typography>
//     </Box>
//   );
// };
//
//
export const DocumentView: React.FC<{ data: ParsedCall<WeaveDocumentSchema>, isExpanded: boolean}> = ({ data }) => {
  const [inputsExpanded, setInputsExpanded] = useState(true);
  const [outputsExpanded, setOutputExpanded] = useState(true);

  const {inputsDocuments, outputDocuments} = useMemo(() => {
    const inputs = data.inputs?.filter(parsed => parsed.schema == "Document") ?? [];
    const output = data.output?.filter(parsed => parsed.schema == "Document") ?? [];
    return {
      inputsDocuments: inputs.length > 0 ? inputs.flatMap((item) => item.result) : null,
      outputDocuments: output.length > 0 ? output.flatMap((item) => item.result) : null,
    }
  }, [data]);
  return (
    <div>
      {inputsDocuments && <DocumentDropdown title={'Inputs'} documents={inputsDocuments} isExpanded={inputsExpanded} setExpanded={setInputsExpanded} />}
      {outputDocuments && <DocumentDropdown title={'Outputs'} documents={outputDocuments} isExpanded={outputsExpanded} setExpanded={setOutputExpanded}/>}
    </div>
  )
};
