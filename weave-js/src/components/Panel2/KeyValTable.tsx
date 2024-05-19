import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const Table = styled.div`
  font-size: 13px;
  display: table;
  padding: 2px;
  width: 100%;
`;
Table.displayName = 'S.Table';

export const Rows = styled.div`
  margin-top: 2px;
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 2px;
`;
Rows.displayName = 'S.Rows';

export const Row = styled.div`
  display: contents;
  gap: 2px;
`;
Row.displayName = 'S.Row';

export const Key = styled.div`
  white-space: nowrap;
  text-overflow: ellipsis;
  vertical-align: top;
  padding: 0 !important;
  color: ${globals.MOON_500};
  grid-column: 1;
`;
Key.displayName = 'S.Key';

export const Val = styled.div`
  padding: 0 !important;
  grid-column: 2;
  color: ${globals.MOON_800};
`;
Val.displayName = 'S.Val';

export const InputUpdateLink = styled.span`
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
`;
InputUpdateLink.displayName = 'S.InputUpdateLink';
