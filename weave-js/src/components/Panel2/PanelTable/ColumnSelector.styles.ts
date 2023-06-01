import {Input} from 'semantic-ui-react';
import styled from 'styled-components';

export const ColumnSearchInput = styled(Input)`
  width: 100%;
  margin-left: 5px;
  & > input {
    border: none !important;
    border-radius: 0 !important;
    border-bottom: 1px solid #d2d2d2 !important;
  }
`;
