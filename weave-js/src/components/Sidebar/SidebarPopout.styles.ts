import {GLOBAL_COLORS} from '@wandb/weave/common/util/colors';
import styled from 'styled-components';

export const Wrapper = styled.div<{position: {x: number; y: number}}>`
  position: fixed;
  background: white;
  padding: 8px;
  right: ${props => props.position.x}px;
  top: ${props => props.position.y}px;
  border: 1px solid ${GLOBAL_COLORS.outline.toString()};
  border-right: none;
  z-index: 20001;
`;
