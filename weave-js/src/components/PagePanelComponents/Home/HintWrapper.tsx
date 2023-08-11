import React from 'react';
import * as globals from '@wandb/weave/common/css/globals.styles';
import styled, {keyframes} from 'styled-components';

const bounce = keyframes`
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(-50%) translateX(0);
  }
  40% {
    transform: translateY(-50%) translateX(-15px);
  }
  60% {
    transform: translateY(-50%) translateX(-5px);
  }
`;

const Wrapper = styled.div`
  position: relative;
  display: inline-block; /* Adjust this if needed */
`;

const HintArrow = styled.div`
  position: absolute;
  width: 0;
  height: 0;
  border-top: 10px solid transparent;
  border-bottom: 10px solid transparent;
  border-left: 10px solid ${globals.TEAL_LIGHT};
  top: 50%;
  left: -15px;
  transform: translateY(-50%);
  zindex: 10;
  animation: ${bounce} 2s infinite;
`;

export const HintWrapper: React.FC = ({children}) => {
  return (
    <Wrapper>
      {children}
      <HintArrow />
    </Wrapper>
  );
};

export default HintWrapper;
