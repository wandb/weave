import React from 'react';
import * as LayoutElements from './LayoutElements';
import {Button} from '../../Button';
import {Node, Type, callOpVeryUnsafe} from '@wandb/weave/core';
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
import {Panel2Loader} from '../../Panel2/PanelComp';

// This is considered a `hack` because I need to drop down to
// access .tw-style, to give it a height 100%. When using tailwind
// components, the hight is not set and it collapses in this case because
// all children have relative hights.
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

export const HomeFeaturedTemplates: React.FC<{
  setPreviewNode: SetPreviewNodeType;
}> = ({setPreviewNode}) => {
  const featuredTemplatesNode = callOpVeryUnsafe(
    'py_board-get_featured_board_templates',
    {}
  ) as Node;
  const featuredTemplates = useNodeValue(featuredTemplatesNode);
  if (featuredTemplates.result?.length === 0) {
    // not expecting this to happen, but just in case
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
      {featuredTemplates.loading ? (
        <LayoutElements.Block style={{height: '166px'}}>
          <Panel2Loader />
        </LayoutElements.Block>
      ) : (
        <LayoutElements.HStack
          style={{
            gap: '16px',
          }}>
          {featuredTemplates.result.map((template: TemplateType, i: number) => (
            <HomeFeaturedTemplateItem
              key={template.op_name}
              template={template}
              setPreviewNode={setPreviewNode}
            />
          ))}
        </LayoutElements.HStack>
      )}
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
    <LayoutElements.HStack
      style={{
        border: '1px solid #E5E5E5',
        borderRadius: '8px',
        padding: '16px',
        gap: '8px',
      }}>
      {template.thumbnail_url && (
        <LayoutElements.Block
          style={{
            height: '132px',
          }}>
          <img
            src={template.thumbnail_url}
            alt={template.display_name + ' thumbnail'}
            style={{
              height: '100%',
              // width: '100%',
              borderRadius: '4px',
            }}
          />
        </LayoutElements.Block>
      )}
      <LayoutElements.VStack
        style={{
          // gap: '8px',
          flex: 1,
          height: '132px',
        }}>
        <LayoutElements.HBlock
          style={{
            fontSize: '18px',
            fontWeight: 800,
          }}>
          {template.display_name}
        </LayoutElements.HBlock>
        <LayoutElements.HStack
          style={{
            overflow: 'auto',
          }}>
          {template.description}
        </LayoutElements.HStack>
        <LayoutElements.HBlock
          style={{
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
    </LayoutElements.HStack>
  );
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
