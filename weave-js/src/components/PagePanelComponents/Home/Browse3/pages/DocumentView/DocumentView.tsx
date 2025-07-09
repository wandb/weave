import { Box, Collapse } from '@mui/material';
import { Button } from '@wandb/weave/components/Button';
import React, { useMemo, useState } from 'react';

import { MetadataViewerSection } from './MetadataViewerSection';
import {ParsedCall, WeaveDocumentSchema} from './schemas';
import {Body,Header} from './Styles';

interface DocumentCardProps {
  doc: WeaveDocumentSchema;
}

const DocumentCard: React.FC<DocumentCardProps> = ({ doc }) => {
  const metadata = useMemo(() => {
    if (doc.metadata && typeof doc.metadata === 'object' && doc.content) {
      return doc.metadata;
    }
    return null;
  }, [doc]);

  return (
    <Box
      border={1}
      borderColor={"#DFE0E2"}
      borderRadius={"8px"}
      paddingX={"20px"}
      paddingY={"16px"}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8}}>
        <Body>
          {doc.content}
        </Body>
        {metadata && (
          <MetadataViewerSection
            title={"Metadata"}
            data={metadata}
            open={false}
          />
        )}
      </div>
    </Box>
  );
};

interface DocumentDropdownProps {
  documents: WeaveDocumentSchema[];
  title: string;
}

const DocumentDropdown: React.FC<DocumentDropdownProps> = ({ documents, title }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', height: 'auto'}}>
      <div style={{ display: 'flex', marginBottom: '4px' }}>
        <Header>{title}</Header>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
        {documents.map((doc, index) => (
          <div key={index} style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
            <DocumentCard doc={doc} />
          </div>
        ))}
      </div>
    </div>
  );
};


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
