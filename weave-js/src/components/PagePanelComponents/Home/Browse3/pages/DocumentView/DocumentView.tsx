
import React, { Fragment, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, Typography } from '@mui/material';
import { ParsedCall, WeaveDocumentSchema } from './schemas';
import { ObjectViewerSection } from '../CallPage/ObjectViewerSection';

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
    <Card>
      <CardContent>
        <Typography variant="body2" color="text.secondary">
          {doc.content}
        </Typography>
        {metadata && (
          <ObjectViewerSection
            title="Metadata"
            data={metadata}
            isExpanded={false}
          />
        )}
      </CardContent>
    </Card>
  );
};


export const DocumentList: React.FC<{title: string, documents: WeaveDocumentSchema[], expanded?: boolean}> = ({ title, documents, expanded }) => {
  return (
    <Fragment>
      <li>
        {documents.map((doc) => <DocumentCard doc={doc} />)}
      </li>
    </Fragment> 
  )
}
export const DocumentView: React.FC<{ data: ParsedCall<WeaveDocumentSchema, 'Document'>}> = ({ data }) => {
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
      {inputsDocuments && <DocumentList title={'Inputs'} documents={inputsDocuments}/>}
      {outputDocuments && <DocumentList title={'Output'} documents={outputDocuments}/>}
    </div>
  )
};
