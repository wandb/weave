import styled from 'styled-components';

const STYLE_DEBUG = false;

const debug_style = `
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
  ${debug_style}
`;

export const HStack = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;

export const Space = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  ${debug_style}
`;

export const Block = styled.div`
  flex: 0 0 auto;
  ${debug_style}
`;

export const VSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  ${debug_style}
`;

export const HSpace = styled.div`
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 auto;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;

export const VBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  ${debug_style}
`;

export const HBlock = styled.div`
  flex: 0 0 auto;
  display: flex;
  flex-direction: row;
  ${debug_style}
`;
