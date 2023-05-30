import Markdown from '@wandb/weave/common/components/Markdown';
import * as Op from '@wandb/weave/core';
import React from 'react';

import * as CGReact from '../../../react';
import * as Panel2 from '../panel';
import {inputType} from './common';

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
    <div style={{height: '100%', overflow: 'scroll'}}>
      <div
        style={{
          background: 'white',
          border: '1px solid #eee',
          padding: 16,
        }}>
        <Markdown condensed={false} content={content} />
      </div>
    </div>
  );
};

export default PanelFileMarkdown;
