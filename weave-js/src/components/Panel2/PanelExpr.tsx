import React from 'react';
import styled from 'styled-components';

import * as Colors from '../../common/css/color.styles';
import * as Panel2 from './panel';

const inputType = 'any';

type PanelExpressionProps = Panel2.PanelProps<typeof inputType>;

const Container = styled.div`
  height: 100%;
  color: ${Colors.MOON_450};
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-style: normal;
  font-family: Source Sans Pro;
  line-height: 24px;
  gap: 12px;
`;
Container.displayName = 'S.Container';

const Primary = styled.div`
  font-size: 20px;
  font-weight: 600;
`;
Primary.displayName = 'S.Primary';

const Secondary = styled.div`
  font-size: 16px;
  font-weight: 400;
`;
Secondary.displayName = 'S.Secondary';

export const PanelExpression: React.FC<PanelExpressionProps> = props => {
  return (
    <Container>
      <Primary>Empty panel</Primary>
      <Secondary>Open the panel editor to configure.</Secondary>
    </Container>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'Expression',
  icon: 'code-alt',
  Component: PanelExpression,
  inputType,
  hidden: true,
};
