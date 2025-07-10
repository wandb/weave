import React, {useMemo} from 'react';

import {MetadataViewerSection} from './MetadataViewerSection';
import {ParsedCall, WeaveDocument} from './schemas';
import {Body, Header} from './StyledText';

interface DocumentCardProps {
  doc: WeaveDocument;
}

const DocumentCard: React.FC<DocumentCardProps> = ({doc}) => {
  const metadata = useMemo(() => {
    if (doc.metadata && typeof doc.metadata === 'object' && doc.content) {
      return doc.metadata;
    }
    return null;
  }, [doc]);

  return (
    <div className="tw-style rounded-lg border border-moon-250 px-20 py-16">
      <div className="flex flex-col gap-8">
        <Body>{doc.content}</Body>
        {metadata && (
          <MetadataViewerSection
            title={'Metadata'}
            data={metadata}
            open={false}
          />
        )}
      </div>
    </div>
  );
};

interface DocumentDropdownProps {
  documents: WeaveDocument[];
  title: string;
}

const DocumentDropdown: React.FC<DocumentDropdownProps> = ({
  documents,
  title,
}) => {
  return (
    <div className="tw-style flex h-auto w-full flex-col gap-8">
      <div className="mb-4 flex">
        <Header>{title}</Header>
      </div>
      <div className="flex flex-col gap-16">
        {documents.map((doc, index) => (
          <div key={index} className="flex flex-col gap-16">
            <DocumentCard doc={doc} />
          </div>
        ))}
      </div>
    </div>
  );
};

export const DocumentView: React.FC<{
  data: ParsedCall<WeaveDocument>;
}> = ({data}) => {
  const {inputsDocuments, outputDocuments} = useMemo(() => {
    const inputs =
      data.inputs?.filter(parsed => parsed.schema === 'Document') ?? [];
    const output =
      data.output?.filter(parsed => parsed.schema === 'Document') ?? [];
    return {
      inputsDocuments:
        inputs.length > 0 ? inputs.flatMap(item => item.result) : null,
      outputDocuments:
        output.length > 0 ? output.flatMap(item => item.result) : null,
    };
  }, [data]);

  return (
    <div className="tw-style flex flex-col gap-16">
      {inputsDocuments && (
        <DocumentDropdown title={'Inputs'} documents={inputsDocuments} />
      )}
      {outputDocuments && (
        <DocumentDropdown title={'Outputs'} documents={outputDocuments} />
      )}
    </div>
  );
};
