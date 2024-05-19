import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const OpNameRow = styled.div`
  display: flex;
  height: 24px;
`;
OpNameRow.displayName = 'S.OpNameRow';

export const OpName = styled.h2`
  flex: 1 1 auto;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
`;
OpName.displayName = 'S.OpName';

export const OpClose = styled.div`
  margin-left: 10px;
`;
OpClose.displayName = 'S.OpClose';

export const Section = styled.div`
  margin-bottom: 8px;
`;

export const Subheader = styled.h3`
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 2px;
`;

export const Markdown = styled.div`
  font-size: 14px;
  color: ${globals.MOON_250};
`;

export const ArgList = styled.ul`
  margin: 0;
  list-style-type: none;
  padding-left: 16px;

  li {
    margin-bottom: 4px;
    line-height: 1em;
  }
`;

export const ArgName = styled.span`
  font-size: 14px;
  font-weight: 600;
`;

export const Code = styled.code`
  font-family: Inconsolata;
`;
