import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

export const Table = styled.div`
  font-size: 13px;

  padding: 2px;
`;
Table.displayName = 'S.Table';

export const Rows = styled.div`
  display: grid;
  grid-template-columns: max-content 1fr;
`;
Rows.displayName = 'S.Rows';

export const Row = styled.div`
  display: contents;
`;
Row.displayName = 'S.Row';

export const Key = styled.div`
  white-space: nowrap;
  padding: 0 !important;
  color: ${globals.gray500};
  grid-column: 1;
`;
Key.displayName = 'S.Key';

export const Val = styled.div`
  grid-column: 2;
`;
Val.displayName = 'S.Val';

export const InputUpdateLink = styled.span`
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
`;
InputUpdateLink.displayName = 'S.InputUpdateLink';
