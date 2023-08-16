import React from 'react';
import styled from 'styled-components';
import {IconWeaveLogo} from '../../Panel2/Icons';

export const HomeTopBar: React.FC = () => {
  return (
    <TopBar>
      <TopBarLeft>
        <WeaveLogo />
        Weave
      </TopBarLeft>
    </TopBar>
  );
};

const TopBar = styled.div`
  height: 64px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const TopBarLeft = styled.div`
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  margin-right: 12px;
`;
