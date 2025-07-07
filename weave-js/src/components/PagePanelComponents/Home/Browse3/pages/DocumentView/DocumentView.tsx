import React, {useMemo} from 'react';
import {ParsedCall, WeaveDocumentSchema} from './schemas';
import {DocumentDropdown} from './DropdownMenu';

export const DocumentView: React.FC<{ data: ParsedCall<WeaveDocumentSchema>, isExpanded: boolean}> = ({ data }) => {
  const {inputsDocuments, outputDocuments} = useMemo(() => {
    const inputs = data.inputs?.filter(parsed => parsed.schema == "Document") ?? [];
    const output = data.output?.filter(parsed => parsed.schema == "Document") ?? [];
    return {
      inputsDocuments: inputs.length > 0 ? inputs.flatMap((item) => item.result) : null,
      outputDocuments: output.length > 0 ? output.flatMap((item) => item.result) : null,
    }
  }, [data]);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
      {inputsDocuments && <DocumentDropdown title={'Inputs'} documents={inputsDocuments} />}
      {outputDocuments && <DocumentDropdown title={'Outputs'} documents={outputDocuments} />}
    </div>
  )
};
