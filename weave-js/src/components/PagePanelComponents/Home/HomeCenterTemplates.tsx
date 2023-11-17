import {
  MOON_250,
  MOON_350,
  MOON_500,
} from '@wandb/weave/common/css/color.styles';
import {opGetFeaturedBoardTemplates, Type} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React from 'react';
import styled from 'styled-components';

import {Button} from '../../Button';
import {Panel2Loader} from '../../Panel2/PanelComp';
import {SetPreviewNodeType} from './common';
import {HomeFeaturedTemplateDrawer} from './HomeFeaturedTemplates';
import {HomePreviewSidebarTemplate} from './HomePreviewSidebar';
import * as LayoutElements from './LayoutElements';

const Template = styled(LayoutElements.VStack)`
  width: 332px;
  height: 368px;
  padding: 16px;
  border-radius: 4px;
  border: 1px solid ${MOON_250};
  gap: 16px;
  overflow-y: auto;
  &:hover {
    border: 1px solid ${MOON_350};
    box-shadow: 0px 4px 8px 0px rgba(14, 16, 20, 0.04);
  }
`;
Template.displayName = 'S.Template';

const TemplateDescription = styled(LayoutElements.Block)`
  overflow: hidden;
  color: ${MOON_500};
  text-overflow: ellipsis;
  font-family: Source Sans Pro;
  font-size: 14px;
  font-style: normal;
  font-weight: 400;
  line-height: 140%;
`;
TemplateDescription.displayName = 'S.TemplateDescription';

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
  const featuredTemplatesNode = opGetFeaturedBoardTemplates({});
  const featuredTemplates = useNodeValue(featuredTemplatesNode);
  if (featuredTemplates.result?.length === 0) {
    // not expecting this to happen, but just in case
    return null;
  }
  return (
    <LayoutElements.VBlock
      style={{padding: '32px', gap: '32px', height: '100%'}}>
      <LayoutElements.HBlock>
        <div style={{fontWeight: '600', fontSize: '24px'}}>Board templates</div>
      </LayoutElements.HBlock>
      {featuredTemplates.loading ? (
        <LayoutElements.Block>
          <Panel2Loader />
        </LayoutElements.Block>
      ) : (
        <LayoutElements.HStack
          style={{gap: '32px', flexWrap: 'wrap', overflow: 'auto'}}>
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
    <Template
      data-testid="template-card"
      onMouseEnter={() => {
        setIsHover(true);
      }}
      onMouseLeave={() => {
        setIsHover(false);
      }}>
      {template.thumbnail_url && (
        <LayoutElements.Block style={{height: '168px'}}>
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
      <TemplateDescription>{template.description}</TemplateDescription>
      <LayoutElements.Block style={{width: '100%', marginTop: 'auto'}}>
        {isHover && (
          <Button
            className="w-full"
            onClick={() => {
              setPreviewNode(node, '35%');
            }}>
            Try it out
          </Button>
        )}
      </LayoutElements.Block>
    </Template>
  );
};
