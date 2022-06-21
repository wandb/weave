import React from 'react';
import Markdown from '@wandb/common/components/Markdown';

import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';

const inputType = {
  type: 'union' as const,
  members: ['md', 'markdown'].map(extension => ({
    type: 'file' as const,
    extension,
  })),
};

type PanelFileMarkdownProps = Panel2.PanelProps<typeof inputType>;

const PanelFileMarkdown: React.FC<PanelFileMarkdownProps> = props => {
  const contentsNode = Op.opFileContents({file: props.input});
  const contentsValueQuery = CGReact.useNodeValue(contentsNode);
  if (contentsValueQuery.loading) {
    return <div></div>;
  }

  const content = contentsValueQuery.result;
  if (content == null) {
    throw new Error('PanelFileMarkdown: content is null');
  }

  return (
    <div
      style={{
        background: 'white',
        border: '1px solid #eee',
        padding: 16,
      }}>
      <pre
        style={{
          maxWidth: '100%',
          overflowX: 'auto',
          textOverflow: 'ellipsis',
        }}>
        <Markdown condensed={false} content={content} />
      </pre>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'markdown',
  Component: PanelFileMarkdown,
  inputType,
};
