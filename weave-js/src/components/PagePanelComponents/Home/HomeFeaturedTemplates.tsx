import './github-markdown-light.css';

import {TargetBlank} from '@wandb/weave/common/util/links';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Type} from '@wandb/weave/core';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import {Prism as SyntaxHighlighter} from 'react-syntax-highlighter';
import remarkGfm from 'remark-gfm';
import styled from 'styled-components';

import * as LayoutElements from './LayoutElements';

// This is considered a `hack` because I need to drop down to
// access .tw-style, to give it a height 100%. When using tailwind
// components, the height is not set and it collapses in this case because
// all children have relative heights.
const TWDrawerHack = styled.div`
  height: 100%;
  overflow: hidden;
  .tw-style {
    height: 100%;
  }
`;
TWDrawerHack.displayName = 'S.TWDrawerHack';

type TemplateType = {
  config_type: Type | null;
  description: string;
  display_name: string;
  op_name: string;
  instructions_md: string;
  thumbnail_url?: string;
};

const TabContentWrapper = styled.div`
  overflow-y: scroll;
  padding: 16px;
  // Another reason I can't stand tailwind
  height: calc(100% - 32px);
  .markdown-body {
    ul {
      list-style: unset !important;
    }
  }
`;
TabContentWrapper.displayName = 'S.TabContentWrapper';

export const HomeFeaturedTemplateDrawer: React.FC<{
  template: TemplateType;
}> = ({template}) => {
  const [tabValue, setTabValue] = React.useState('Instructions');
  return (
    <TWDrawerHack>
      <LayoutElements.VBlock
        style={{
          height: '100%',
          overflow: 'hidden',
        }}>
        <Tabs.Root
          className="h-full"
          value={tabValue}
          onValueChange={(val: string) => setTabValue(val)}>
          <Tabs.List className="px-16">
            <Tabs.Trigger value="Instructions">1. Instructions</Tabs.Trigger>
            {/*
              <Tabs.Trigger value="Select Data">2. Select Data</Tabs.Trigger>
              NOTE: Once we have the interactive data flow we can re-enable this tab.
            */}
          </Tabs.List>
          <Tabs.Content value="Instructions" style={{height: '100%'}}>
            <TabContentWrapper>
              <ReactMarkdown
                components={{
                  // Ensures that links open in a new tab
                  a: ({node, ...props}) => {
                    return <TargetBlank {...props} />;
                  },
                  code: ({node, inline, className, children, ...props}) => {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <SyntaxHighlighter
                        {...(props as any)}
                        children={String(children).replace(/\n$/, '')}
                        language={match[1]}
                        PreTag="div"
                      />
                    ) : (
                      <code {...props} className={className}>
                        {children}
                      </code>
                    );
                  },
                }}
                remarkPlugins={[[remarkGfm]]}
                className="markdown-body">
                {template.instructions_md}
              </ReactMarkdown>
            </TabContentWrapper>
          </Tabs.Content>
          <Tabs.Content value="Select Data">
            <TabContentWrapper>
              Once you've logged your data, use the browser on your left to find
              your table. From there, choose a template to get started!
            </TabContentWrapper>
          </Tabs.Content>
        </Tabs.Root>
      </LayoutElements.VBlock>
    </TWDrawerHack>
  );
};
