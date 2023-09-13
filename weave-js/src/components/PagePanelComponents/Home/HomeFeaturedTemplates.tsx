import React from 'react';
import * as LayoutElements from './LayoutElements';
import {Button} from '../../Button';
import {Type, callOpVeryUnsafe} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';

import {HomePreviewSidebarTemplate} from './HomePreviewSidebar';
import {SetPreviewNodeType} from './common';

type TemplateType = {
  config_type: Type | null;
  description: string;
  display_name: string;
  op_name: string;
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
      actions={[]}>
      <HomeFeaturedTemplateDrawer />
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

const HomeFeaturedTemplateDrawer: React.FC<{}> = props => {
  return (
    <LayoutElements.VStack>
      <LayoutElements.Block
        style={{
          padding: '12px 12px',
          fontSize: '18px',
          fontWeight: 800,
        }}>
        Template instructions
      </LayoutElements.Block>
    </LayoutElements.VStack>
  );
};
