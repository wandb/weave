import { Box, Collapse, IconButton, Stack, Table, TableBody, TableCell,TableRow, Typography } from '@mui/material';
import { Button } from '@wandb/weave/components/Button';
import React, { useMemo, useState } from 'react';
import styled from 'styled-components';

import { ObjectViewerSection } from '../CallPage/ObjectViewerSection';
import { WeaveDocumentSchema } from './schemas';
// import { ObjectViewerSection } from './MetadataTable';

interface DropdownSectionProps {
  title: string;
  children: React.ReactNode;
  defaultExpanded: boolean;
}

const TitleRow = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 4px;
`;
TitleRow.displayName = 'S.TitleRow';

const Title = styled.div`
  font-family: Source Sans Pro;
  font-style: SemiBold
  font-size: 16px;
  font-weight: 600;
  line-height: 100%;
  letter-spacing: 0px;
  color: #2B3038
`;
Title.displayName = 'S.Title';

export const DropdownSection: React.FC<DropdownSectionProps> = ({
  title,
  children,
  defaultExpanded,
}) => {
  const [isExpanded, setExpanded] = useState(defaultExpanded);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', height: 'auto'}}>
      <TitleRow>
        <Button
          onClick={() => { setExpanded(!isExpanded); }}
          variant='ghost'
          size='small'
          icon={isExpanded ? "chevron-down" : "chevron-next"}
        />
        <Title>{title}</Title>
      </TitleRow>
      <Collapse in={isExpanded}>
        <Box>
          {children}
        </Box>
      </Collapse>
    </div>
  );
};

interface MetadataTableProps {
  data: Record<string, any>;
}

export const MetadataTable: React.FC<MetadataTableProps> = ({ data }) => {
  return (
    <Table size="small">
      <TableBody>
        {Object.entries(data).map(([key, value], index) => (
          <TableRow key={key}>
            <TableCell
              component="th"
              scope="row"
              sx={{ 
                fontWeight: 500,
                color: 'text.secondary',
                width: '30%',
                borderTop: index > 0 ? '1px solid' : '0px',
                borderBottom: index < data.length - 1 ? '1px solid' : '0px',
                borderColor: 'divider',
              }}
            >
              {key}
            </TableCell>
            <TableCell 
              sx={{
                borderTop: index > 0 ? '1px solid' : '0px',
                borderBottom: index < data.length - 1 ? '1px solid' : '0px',
              }}
            >
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

interface DocumentCardProps {
  doc: WeaveDocumentSchema;
}
export const DocumentCard: React.FC<DocumentCardProps> = ({ doc }) => {
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
      paddingTop={"12px"}
      paddingLeft={"16px"}
      paddingBottom={"12px"}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8}}>
        <Typography variant="body2" color="text.secondary">
          {doc.content}
        </Typography>
        {metadata && (
          <ObjectViewerSection
            title={"Metadata"}
            data={metadata}
            noHide={true}
            isExpanded={false}
            collapseTitle={true}
            showMinimal={true}
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

export const DocumentDropdown: React.FC<DocumentDropdownProps> = ({ documents, title }) => {
  return (
    <Box>
      <DropdownSection title={title} defaultExpanded={true}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
          {documents.map((doc, index) => (
            <div key={index} style={{ display: 'flex', flexDirection: 'column', gap: 16}}>
              <DocumentCard doc={doc} />
            </div>
          ))}
        </div>
      </DropdownSection>
    </Box>
  );
};
