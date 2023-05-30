import {WBIcon} from '@wandb/ui';
import {Table} from 'semantic-ui-react';
import styled from 'styled-components';

import * as globals from '../css/globals.styles';

export const FileTableBody = styled(Table.Body)`
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
`;

export const SearchRow = styled.tr`
  cursor: unset !important;
  background-color: white !important;

  &:hover {
    background-color: white !important;
  }

  td {
    cursor: unset !important;
    padding: 0 !important;
    overflow: hidden;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
  }
`;

export const NoResultsRow = styled.tr`
  height: 51px;
`;

export const NoResultsMessage = styled.div`
  display: flex;
  height: 51px;
  background-color: white;
  cursor: initial;
  border-top: 1px solid rgb(219, 219, 219);
  align-items: center;
  color: rgba(0, 0, 0, 0.5);
  justify-content: center;
  font-size: 16px;
`;

export const SearchInputContainer = styled.span`
  width: 100%;
  color: ${globals.gray800};
  position: relative;
  background-color: white;
  display: flex;
  padding: 13px;

  input {
    border: none;
    outline: none;
    color: ${globals.gray800};
    background-color: transparent;
    padding: 0 0 0 32px;
    z-index: 1;
    flex: 1 0 auto;
  }
`;

export const SearchInputIcon = styled(WBIcon)`
  color: ${globals.gray500};
  width: 24px;
  font-size: 28px;
  position: absolute;
  top: 7px;
`;
