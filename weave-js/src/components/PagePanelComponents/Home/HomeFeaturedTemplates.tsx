import React from 'react';
import * as LayoutElements from './LayoutElements';
import {Button} from '../../Button';
import {Type, callOpVeryUnsafe} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import * as Tabs from '@wandb/weave/components/Tabs';

import {HomePreviewSidebarTemplate} from './HomePreviewSidebar';
import {SetPreviewNodeType} from './common';
import styled from 'styled-components';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import './github-markdown-light.css';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {Prism as SyntaxHighlighter} from 'react-syntax-highlighter';
// import {dark} from 'react-syntax-highlighter/dist/esm/styles/prism';

const TWDrawerHack = styled.div`
  height: 100%;
  overflow: hidden;
  .tw-style {
    height: 100%;
  }
`;

type TemplateType = {
  config_type: Type | null;
  description: string;
  display_name: string;
  op_name: string;
  instructions_md: string;
};

export const HomeFeaturedTemplates: React.FC<{
  setPreviewNode: SetPreviewNodeType;
}> = ({setPreviewNode}) => {
  const featuredTemplatesNode = callOpVeryUnsafe(
    'py_board-get_featured_board_templates',
    {}
  );
  const featuredTemplates = useNodeValue(featuredTemplatesNode as any);
  if (featuredTemplates.loading || featuredTemplates.result.length === 0) {
    return null;
  }
  return (
    <LayoutElements.VBlock
      style={{
        padding: '0px 12px 24px 12px',
      }}>
      <LayoutElements.HBlock>
        <LayoutElements.BlockHeader
          style={{
            padding: '12px 12px',
          }}>
          FEATURED TEMPLATES
        </LayoutElements.BlockHeader>
      </LayoutElements.HBlock>
      <LayoutElements.HStack
        style={{
          gap: '16px',
        }}>
        {featuredTemplates.result.map((template: any, i: number) => (
          <HomeFeaturedTemplateItem
            key={i}
            template={template}
            setPreviewNode={setPreviewNode}
          />
        ))}
      </LayoutElements.HStack>
    </LayoutElements.VBlock>
  );
};

const HomeFeaturedTemplateItem: React.FC<{
  template: TemplateType;
  setPreviewNode: SetPreviewNodeType;
}> = ({template, setPreviewNode}) => {
  const node = (
    <HomePreviewSidebarTemplate
      title={template.display_name}
      setPreviewNode={setPreviewNode}
      isTemplate={true}
      actions={[]}>
      <HomeFeaturedTemplateDrawer template={template} />
    </HomePreviewSidebarTemplate>
  );

  return (
    <LayoutElements.VStack
      style={{
        border: '1px solid #E5E5E5',
        borderRadius: '8px',
        padding: '16px',
        gap: '8px',
      }}>
      <LayoutElements.HBlock
        style={{
          fontSize: '18px',
          fontWeight: 800,
        }}>
        {template.display_name}
      </LayoutElements.HBlock>
      <LayoutElements.HStack>{template.description}</LayoutElements.HStack>
      <LayoutElements.HBlock
        style={{
          marginTop: '12px',
          justifyContent: 'flex-end',
        }}>
        <Button
          variant="secondary"
          size="medium"
          onClick={() => {
            setPreviewNode(node, '40%');
          }}>
          Use template
        </Button>
      </LayoutElements.HBlock>
    </LayoutElements.VStack>
  );
};

const TabContentWrapper = styled.div`
  overflow-y: scroll;
  padding: 16px;
  height: 100%;
  .markdown-body {
    ul {
      list-style: unset !important;
    }
  }
`;
TabContentWrapper.displayName = 'S.TabContentWrapper';

const HomeFeaturedTemplateDrawer: React.FC<{
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
            <Tabs.Trigger value="Select Data">2. Select Data</Tabs.Trigger>
          </Tabs.List>
          <Tabs.Content value="Instructions" style={{height: '100%'}}>
            <TabContentWrapper>
              <ReactMarkdown
                components={{
                  // Ensures that links open in a new tab
                  a: ({node, ...props}) => {
                    return <TargetBlank {...props} />;
                  },
                  code({node, inline, className, children, ...props}) {
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
