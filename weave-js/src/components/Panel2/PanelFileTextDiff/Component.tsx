import 'prismjs/components/prism-python';

import {
  applyOpToOneOrMany,
  isFile,
  listObjectType,
  nullableTaggableValue,
  opFileContents,
  opFileSize,
} from '@wandb/weave/core';
import numeral from 'numeral';
import Prism from 'prismjs';
import React from 'react';
import ReactDiffViewer, {DiffMethod} from 'react-diff-viewer';
import {Segment} from 'semantic-ui-react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import * as PanelFileText from '../PanelFileText';
import {inputType} from './common';

const FILE_SIZE_LIMIT = 25 * 1024 * 1024;
const LINE_LENGTH_LIMIT = 500;
const TOTAL_LINES_LIMIT = 1000;

type PanelFileTextCompareProps = Panel2.PanelProps<typeof inputType>;

const PanelFileTextCompareViewer: React.FC<{
  fileContents: Array<{extension: string; text: string}>;
}> = props => {
  const processedResults = React.useMemo(
    () =>
      props.fileContents.map(content =>
        PanelFileText.processTextForDisplay(
          content.extension,
          content.text,
          LINE_LENGTH_LIMIT,
          TOTAL_LINES_LIMIT
        )
      ),
    [props.fileContents]
  );

  const truncatedTotalLines = React.useMemo(
    () => processedResults.some(pr => pr.truncatedTotalLines),
    [processedResults]
  );
  const truncatedLineLength = React.useMemo(
    () => processedResults.some(pr => pr.truncatedLineLength),
    [processedResults]
  );
  const data = React.useMemo(
    () => processedResults.map(pr => pr.text),
    [processedResults]
  );

  const highlightSyntax = (str: string) => (
    <pre
      style={{display: 'inline'}}
      dangerouslySetInnerHTML={{
        __html: Prism.highlight(str || '', Prism.languages.python, 'python'),
      }}
    />
  );

  return (
    <div style={{width: '100%', height: '100%', overflowY: 'auto'}}>
      {truncatedLineLength && (
        <Segment textAlign="center">
          Warning: some lines truncated to {LINE_LENGTH_LIMIT} characters for
          display
        </Segment>
      )}
      {truncatedTotalLines && (
        <Segment textAlign="center">
          Warning: truncated to {TOTAL_LINES_LIMIT} lines for display
        </Segment>
      )}
      {(truncatedLineLength || truncatedTotalLines) &&
        props.fileContents.length >= 2 &&
        props.fileContents[0].text !== props.fileContents[1].text && (
          <Segment textAlign="center">
            Warning: Files differ but we truncated the content prior to diffing.
            Diff display may not show all mismatches.
          </Segment>
        )}
      <ReactDiffViewer
        oldValue={data[0] ?? undefined}
        newValue={data[1] ?? undefined}
        renderContent={highlightSyntax}
        compareMethod={DiffMethod.WORDS}
        styles={{
          contentText: {
            overflow: 'hidden',
          },
        }}
      />
    </div>
  );
};

const PanelFileTextCompareContents: React.FC<
  PanelFileTextCompareProps
> = props => {
  const inputNode = props.input;
  const fileContentsNode = applyOpToOneOrMany(
    opFileContents,
    'file',
    inputNode as any,
    {}
  );
  const fileContents = CGReact.useNodeValue(fileContentsNode);
  const finalFileContents = React.useMemo(() => {
    const fileType = nullableTaggableValue(listObjectType(inputNode.type));
    const extension =
      isFile(fileType) && fileType.extension != null ? fileType.extension : '';

    return ((fileContents.result ?? []) as string[]).map(text => {
      return {
        extension,
        text,
      };
    });
  }, [fileContents.result, inputNode.type]);
  if (fileContents.loading) {
    return <div></div>;
  } else {
    return <PanelFileTextCompareViewer fileContents={finalFileContents} />;
  }
};

const PanelFileTextCompareSizeGuard: React.FC<{sizes: number[]}> = props => {
  const largeFiles = props.sizes.filter(size => (size ?? 0) > FILE_SIZE_LIMIT);
  if (largeFiles.length > 0) {
    return (
      <Segment textAlign="center">
        Text view limited to files less than{' '}
        {numeral(FILE_SIZE_LIMIT).format('0.0b')}
      </Segment>
    );
  } else {
    return <>{props.children}</>;
  }
};

const PanelFileTextCompare: React.FC<PanelFileTextCompareProps> = props => {
  const filesSizesNode = applyOpToOneOrMany(
    opFileSize,
    'file',
    props.input as any,
    {}
  );
  const filesSizes = CGReact.useNodeValue(filesSizesNode);

  if (filesSizes.loading) {
    return <div></div>;
  } else {
    return (
      <PanelFileTextCompareSizeGuard sizes={filesSizes.result}>
        <PanelFileTextCompareContents {...props} />
      </PanelFileTextCompareSizeGuard>
    );
  }
};

export default PanelFileTextCompare;
