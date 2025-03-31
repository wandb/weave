import {Button, Checkbox, Dropdown} from 'semantic-ui-react';
import styled from 'styled-components';

// Styled components for the filter UI
export const FilterContainer = styled.div`
  display: flex;
  flex-direction: column;
  min-width: 600px;
  max-width: 900px;
  width: max-content;
  padding: 16px;
  background-color: white;
  position: fixed;
  z-index: 1000;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
`;

export const FilterRow = styled.div`
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  gap: 10px;
  width: 100%;
  padding: 8px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  min-width: 0;
`;

export const FilterCheckbox = styled(Checkbox)`
  margin-right: 8px !important;
  &.ui.checkbox input:checked ~ .box:after,
  &.ui.checkbox input:checked ~ label:after {
    color: #4ab5c1 !important;
  }
`;

export const FilterContent = styled.div<{disabled: boolean}>`
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  opacity: ${props => (props.disabled ? 0.5 : 1)};
  pointer-events: ${props => (props.disabled ? 'none' : 'auto')};
  min-width: 0;
`;

export const ColumnSelector = styled(Dropdown)`
  flex: 2;
  min-width: 120px;
  min-height: 32px;
  border: 1px solid #e0e0e0;
  border-radius: 4px !important;
  background: white;
  &.ui.selection.dropdown {
    min-height: 32px;
    padding: 4px 10px;
    font-size: 13px;
    display: flex;
    align-items: center;
  }
  .text {
    font-size: 13px;
    line-height: 24px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
`;

export const OperatorSelector = styled(Dropdown)`
  width: 40px;
  min-width: 40px;
  border: 1px solid #e0e0e0;
  border-radius: 4px !important;
  background: white;
  &.ui.selection.dropdown {
    min-height: 32px;
    padding: 4px 10px;
    font-size: 13px;
    display: flex;
    align-items: center;
  }
  .menu {
    width: auto !important;
  }
  .text {
    font-size: 13px;
    text-align: center;
    line-height: 24px;
  }
`;

export const ValueInput = styled(Dropdown)`
  flex: 3;
  min-width: 150px;
  height: 32px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: white;
  &.ui.selection.dropdown {
    min-height: 32px;
    padding: 4px 12px;
    font-size: 13px;
    display: flex;
    align-items: center;
  }
  .text {
    font-size: 13px;
    line-height: 24px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .menu {
    width: 100% !important;
    max-width: none !important;
  }
  input.search {
    height: 30px !important;
    font-size: 13px !important;
    padding: 4px 12px !important;
    border: none !important;
  }
`;

export const ButtonContainer = styled.div`
  display: flex;
  justify-content: flex-start;
  margin-top: 16px;
  margin-bottom: 20px;
`;

export const AddFilterButton = styled(Button)`
  &.ui.button {
    background-color: #4ab5c1;
    color: white;
    height: 34px;
    font-size: 12px;
    padding: 0 16px;
    border-radius: 4px;
    width: auto;

    &:hover {
      background-color: #3da7b3;
    }

    i.icon {
      margin: 0 6px 0 -4px;
      color: white;
      opacity: 1;
    }
  }
`;

export const FooterContainer = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
`;

export const ButtonGroup = styled.div`
  display: flex;
  gap: 10px;
`;

export const ActionButton = styled(Button)`
  &.ui.button {
    height: 34px;
    font-size: 12px;
    padding: 0 20px;
    border-radius: 4px;
    width: auto;
    min-width: 90px;

    &.primary {
      background-color: #4ab5c1;

      &:hover {
        background-color: #3da7b3;
      }
    }
  }
`;

export const AdvancedLink = styled.div`
  text-align: left;
  cursor: pointer;
  color: #666;
  font-size: 12px;
  &:hover {
    text-decoration: underline;
  }
`;
