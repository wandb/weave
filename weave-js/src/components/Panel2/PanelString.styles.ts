import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const StringContainer = styled.div<{
  $spacing?: boolean;
}>`
  padding: ${p => (p.$spacing ? '4px 1em' : '0 1em')};
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
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
StringContainer.displayName = 'S.StringContainer';

export const StringItem = styled.div<{
  $spacing?: boolean;
}>`
  margin: ${p => (p.$spacing ? '0' : 'auto')};
  width: 100%;
  /* padding: 4px; */
  max-height: 100%;
`;
StringItem.displayName = 'S.StringItem';

export const ConfigExpressionWrap = styled.div`
  padding: 0.65em;
  background: white;
  max-width: 20em;
`;
ConfigExpressionWrap.displayName = 'S.ConfigExpressionWrap';

export const PreformattedProportionalString = styled.pre`
  font-family: ${globals.fontName};
  margin-top: 0.25em;
  margin-bottom: 0.25em;
  white-space: pre-wrap;
  line-height: 1.3em;
`;
PreformattedProportionalString.displayName = 'S.PreformattedProportionalString';

export const PreformattedJSONString = styled.pre`
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow: auto;
  font-family: monospace;
`;
PreformattedJSONString.displayName = 'S.PreformattedJSONString';

export const PreformattedMonoString = styled.pre`
  margin-top: 0.25em;
  margin-bottom: 0.25em;
  white-space: pre-wrap;
  line-height: 1.3em;
`;
PreformattedMonoString.displayName = 'S.PreformattedMonoString';

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
TooltipMarkdownTip.displayName = 'S.TooltipMarkdownTip';
