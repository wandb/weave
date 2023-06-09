import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const StringContainer = styled.div`
  padding: 0px 1em;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  overflow-x: auto;
  overflow-y: auto;
  text-align: left;
  // Hide scrollbars
  &::-webkit-scrollbar {
    display: none;
  }
  -ms-overflow-style: none; /* IE and Edge */
  scrollbar-width: none; /* Firefox */
`;

export const StringItem = styled.div`
  margin: auto;
  width: 100%;
  /* padding: 4px; */
  margin: auto;
  max-height: 100%;
`;

export const ConfigExpressionWrap = styled.div`
  padding: 0.65em;
  background: white;
  max-width: 20em;
`;

export const PreformattedProportionalString = styled.pre`
  font-family: ${globals.fontName};
  margin-top: 0.25em;
  margin-bottom: 0.25em;
  white-space: pre-wrap;
  line-height: 1.3em;
`;

export const PreformattedMonoString = styled.pre`
  margin-top: 0.25em;
  margin-bottom: 0.25em;
  white-space: pre-wrap;
  line-height: 1.3em;
`;

export const TooltipMarkdownTip = styled.div`
  padding-bottom: 0.5em;
  color: white;
  font-weight: 500;
  border-bottom: 1px solid gray;
  margin-bottom: 1em;
  &&& button {
    margin: 0px;
    padding: 2px 4px;
  }
`;
