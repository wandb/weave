import React, { useMemo, useState } from 'react';
import { Box, Typography, IconButton, Collapse, Stack, Table, TableBody, TableRow, TableCell } from '@mui/material';
import styled from 'styled-components';
import { Button } from '@wandb/weave/components/Button';
import {ParsedCall, WeaveDocumentSchema} from './schemas';
import { ObjectViewerSection } from '../CallPage/ObjectViewerSection';
import { MetadataViewerSection } from './MetadataViewerSection';
import {Header, Body} from './Styles';

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
  const [isExpanded, setExpanded] = useState(true);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', height: 'auto'}}>
      <div style={{ display: 'flex', marginBottom: '4px' }}>
        <Button
          onClick={() => { setExpanded(!isExpanded); }}
          variant='ghost'
          size='small'
          icon={isExpanded ? "chevron-down" : "chevron-next"}
          style={{fontSize: "16px"}}
        >
          <Header>{title}</Header>
        </Button>
      </div>
      <Collapse in={isExpanded}>
        <Box>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
            {documents.map((doc, index) => (
              <div key={index} style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
                <DocumentCard doc={doc} />
              </div>
            ))}
          </div>
        </Box>
      </Collapse>
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
