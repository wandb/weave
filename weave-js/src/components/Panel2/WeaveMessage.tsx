import * as globals from '@wandb/weave/common/css/globals.styles';
import React from 'react';
import styled from 'styled-components';

const WeaveMessageWrapper = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  font-size: 14px;
  padding: 32px;
  align-items: center;
  align-content: space-around;
  justify-content: space-around;
`;
WeaveMessageWrapper.displayName = 'S.WeaveMessageWrapper';

const WeaveMessageBody = styled.div`
  background: ${globals.errorBackground};
  max-width: 50%;
  padding: 16px;
  > div:not(:last-child) {
    margin-bottom: 8px;
  }
`;
WeaveMessageBody.displayName = 'S.WeaveMessageBody';

export const WeaveMessage: React.FC = ({children}) => {
  return (
    <WeaveMessageWrapper>
      <WeaveMessageBody>{children}</WeaveMessageBody>
    </WeaveMessageWrapper>
  );
};
