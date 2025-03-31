import styled from 'styled-components';

export const PopupContent = styled.div`
  padding: 16px;
`;

export const Label = styled.div`
  margin-bottom: 8px;
  font-weight: 600;
`;

export const FilterControls = styled.div`
  width: 100%;
  position: absolute;
  z-index: 9;
  background: white;
  border-left: 0.5px solid #bbb;
  border-right: 0.5px solid #bbb;
  border-bottom: 0.5px solid #bbb;
  padding: 5px;
  top: 30px;
  display: flex;
  flex-direction: column;
  &.simple-mode {
    padding: 0;
  }
`;
