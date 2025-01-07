import {
  GridEditInputCell,
  GridRenderEditCellParams,
} from '@mui/x-data-grid-pro';
import React from 'react';
import styled from 'styled-components';

const StyledEditCell = styled(GridEditInputCell)`
  textarea {
    height: 100% !important;
    padding: 12px;
    padding-top: 26px;
    font-family: 'Source Sans Pro', sans-serif;
    vertical-align: top;
  }

  .MuiInputBase-root {
    height: 100%;
    align-items: flex-start;
  }

  .MuiInputBase-input {
    height: 100% !important;
  }
`;

const EditableCellRenderer: React.FC<GridRenderEditCellParams> = params => {
  return <StyledEditCell {...params} multiline={true} />;
};

export default EditableCellRenderer;
