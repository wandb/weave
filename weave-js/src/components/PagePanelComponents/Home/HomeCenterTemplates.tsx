import {SetPreviewNodeType} from './common';
import React from 'react';
import * as LayoutElements from './LayoutElements';
import {Button} from 'semantic-ui-react';
import {Node, Type, callOpVeryUnsafe} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {Panel2Loader} from '../../Panel2/PanelComp';

import {HomePreviewSidebarTemplate} from './HomePreviewSidebar';
import {HomeFeaturedTemplateDrawer} from './HomeFeaturedTemplates';
import {
  WHITE,
  TEAL_500,
  MOON_250,
  MOON_350,
} from '@wandb/weave/common/css/color.styles';

type TemplateType = {
  config_type: Type | null;
  description: string;
  display_name: string;
  op_name: string;
  instructions_md: string;
  thumbnail_url?: string;
};

export const HomeCenterTemplates: React.FC<{
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
    <LayoutElements.VBlock style={{padding: '32px', gap: '32px'}}>
      <LayoutElements.HBlock>
        <div style={{fontWeight: '600', fontSize: '24px'}}>Board templates</div>
      </LayoutElements.HBlock>
      {featuredTemplates.loading ? (
        <LayoutElements.Block>
          <Panel2Loader />
        </LayoutElements.Block>
      ) : (
        <LayoutElements.HStack style={{gap: '32px'}}>
          {featuredTemplates.result.map((template: TemplateType, i: number) => (
            <TemplateCard
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

const TemplateCard: React.FC<{
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
  const [isHover, setIsHover] = React.useState(false);
  return (
    <LayoutElements.VStack
      style={{
        width: '300px',
        height: '440px',
        padding: '16px',
        borderRadius: '4px',
        border: `1px solid ${MOON_350}`,
        gap: '16px',
      }}
      onMouseEnter={() => {
        setIsHover(true);
      }}
      onMouseLeave={() => {
        setIsHover(false);
      }}>
      {template.thumbnail_url && (
        <LayoutElements.Block style={{height: '150px'}}>
          <img
            src={template.thumbnail_url}
            alt={template.display_name + ' thumbnail'}
            style={{
              height: '100%',
              width: '100%',
              borderRadius: '4px',
              border: `1px solid ${MOON_250}`,
            }}
          />
        </LayoutElements.Block>
      )}
      <LayoutElements.Block style={{fontWeight: '600', fontSize: '18px'}}>
        {template.display_name}
      </LayoutElements.Block>
      <LayoutElements.Block>{template.description}</LayoutElements.Block>
      <LayoutElements.Block style={{width: '100%', marginTop: 'auto'}}>
        {isHover && (
          <Button
            style={{
              width: '100%',
              backgroundColor: `${TEAL_500}`,
              color: `${WHITE}`,
              borderRadius: '4px',
              fontWeight: '600',
              fontSize: '16px',
            }}
            onClick={() => {
              setPreviewNode(node, '40%');
            }}>
            Use template
          </Button>
        )}
      </LayoutElements.Block>
    </LayoutElements.VStack>
  );
};
