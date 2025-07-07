import React, { useMemo, useState } from 'react';
import { Box, Typography, IconButton, Collapse, Stack, Table, TableBody, TableRow, TableCell } from '@mui/material';
import { ExpandMore, ChevronRight } from '@mui/icons-material';
import styled from 'styled-components';
import { HStack } from '../../../LayoutElements';
import { Button, ButtonVariants } from '@wandb/weave/components/Button';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { WeaveDocumentSchema } from './schemas';

interface DropdownSectionProps {
  title: string;
  children: React.ReactNode;
  isExpanded: boolean,
  setExpanded: (val: boolean) => void;
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
  font-size: 14px;
  font-weight: 600;
  line-height: 100%;
  letter-spacing: 0px;
  color: #2B3038
`;
Title.displayName = 'S.Title';

export const DropdownSection: React.FC<DropdownSectionProps> = ({
  title,
  children,
  isExpanded,
  setExpanded
}) => {
  return (
    <Box onClick={() => setExpanded(!isExpanded)} sx={{ width: '100%', height: 'auto' }}>
      <Button variant='ghost' size='small' icon={isExpanded ? "chevron-down" : "chevron-next"}>
        <Title>{title}</Title>
      </Button>
      <Collapse in={isExpanded}>
        <Box>
          {children}
        </Box>
      </Collapse>
    </Box>
  );
};

interface MetadataTableProps {
  data: Record<string, any>;
}

export const MetadataTable: React.FC<MetadataTableProps> = ({ data }) => {
  return (
    <Table size="small">
      <TableBody>
        {Object.entries(data).map(([key, value]) => (
          <TableRow key={key}>
            <TableCell 
              component="th" 
              scope="row" 
              sx={{ 
                fontWeight: 500, 
                color: 'text.secondary',
                width: '30%',
                borderBottom: '1px solid',
                borderColor: 'divider',
                py: 1.5
              }}
            >
              {key}
            </TableCell>
            <TableCell 
              sx={{ 
                borderBottom: '1px solid',
                borderColor: 'divider',
                py: 1.5
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
  const [metadataExpanded, setMetadataExpanded] = useState(false);
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
      <Typography variant="body2" color="text.secondary">
        {doc.content}
      </Typography>
      {metadata && (
        <Box onClick={(e) => {
          e.stopPropagation();
          setMetadataExpanded(!metadataExpanded);
        }} sx={{ width: '100%', height: 'auto' }}>
          <Button
            variant='ghost'
            size='small'
            icon={metadataExpanded ? "chevron-down" : "chevron-next"}
          >
            <Title>{"Metadata"}</Title>
          </Button>
          <Collapse in={metadataExpanded}>
            <MetadataTable data={metadata} />
          </Collapse>
        </Box>
      )}
    </Box>
  );
};
interface DocumentDropdownProps {
  documents: WeaveDocumentSchema[];
  title: string;
  isExpanded: boolean;
  setExpanded: (val: boolean) => void;
}

export const DocumentDropdown: React.FC<DocumentDropdownProps> = ({ documents, title, isExpanded, setExpanded }) => {
  return (
    <Box>
      <DropdownSection title={title} isExpanded={isExpanded} setExpanded={setExpanded}>
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
