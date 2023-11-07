import React from 'react';
import styled from 'styled-components';

import {IconWeaveLogoGray} from './Icons';

const AnimationWrapper = styled.div`
  @keyframes logo-animation {
    0%,
    100%,
    70% {
      transform: scale(1) rotate(0);
      opacity: 0.6;
    }
    7.5%,
    8% {
      transform: scale(0.75) rotate(0);
      opacity: 0.8;
    }
    25%,
    47.5% {
      transform: scale(1) rotate(180deg);
      opacity: 0.6;
    }
    55%,
    55.5% {
      transform: scale(0.75) rotate(180deg);
      opacity: 0.8;
    }
  }

  opacity: 0.6;
  animation: 4s ease-out infinite logo-animation;
`;

export const WeaveAnimatedLoader: React.FC<{
  style?: React.CSSProperties;
}> = props => {
  const injectStyle = props.style ?? {};
  return (
    <AnimationWrapper style={injectStyle}>
      <IconWeaveLogoGray
        style={{
          width: '100%',
          height: '100%',
        }}
      />
    </AnimationWrapper>
  );
};
