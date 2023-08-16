import {MOON_500} from '@wandb/weave/common/css/color.styles';
import styled from 'styled-components';

const STYLE_DEBUG = false;

const debugStyle = `
  ${
    STYLE_DEBUG
      ? 'background-color: rgba(0,0,0,0.1); border: 1px solid red;'
      : ''
  }
`;

export const VStack = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  ${debugStyle}
`;
VStack.displayName = 'S.VStack';

export const HStack = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  ${debugStyle}
`;
HStack.displayName = 'S.HStack';

export const Space = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  ${debugStyle}
`;
Space.displayName = 'S.Space';

export const Block = styled.div`
  flex: 0 0 auto;
  ${debugStyle}
`;
Block.displayName = 'S.Block';

export const VSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  ${debugStyle}
`;
VSpace.displayName = 'S.VSpace';

export const HSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  ${debugStyle}
`;
HSpace.displayName = 'S.HSpace';

export const VBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  ${debugStyle}
`;
VBlock.displayName = 'S.VBlock';

export const HBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  ${debugStyle}
`;
HBlock.displayName = 'S.HBlock';

export const BlockHeader = styled.div`
  color: ${MOON_500};
  font-weight: 600;
  font-size: 14px;
  line-height: 24px;

  display: flex;
  justify-content: space-between;
`;
BlockHeader.displayName = 'S.BlockHeader';
