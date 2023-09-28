import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const Table = styled.div`
  font-size: 13px;
  display: table;
  padding: 2px;
`;
Table.displayName = 'S.Table';

export const Rows = styled.div`
  margin-top: 2px;
  display: flex;
  flex-direction: column;
  gap: 2px;
`;
Rows.displayName = 'S.Rows';

export const Row = styled.div`
  display: flex;
  gap: 2px;
`;
Row.displayName = 'S.Row';

export const Key = styled.div`
  white-space: nowrap;
  text-overflow: ellipsis;
  vertical-align: top;
  padding: 0 !important;
  color: ${globals.gray500};
  width: 100px;
`;
Key.displayName = 'S.Key';

export const Val = styled.div`
  padding: 0 !important;
`;
Val.displayName = 'S.Val';

export const InputUpdateLink = styled.span`
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
`;
InputUpdateLink.displayName = 'S.InputUpdateLink';
