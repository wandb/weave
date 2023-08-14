import {WBIcon} from '@wandb/ui';
import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';
import {IconButton} from '../IconButton';

export const ColumnHeader = styled.div`
  display: flex;
  align-items: stretch;
  white-space: nowrap;
  justify-content: space-between;
  width: 100%;
  height: 100%;
  .column-actions-trigger {
    visibility: hidden;
  }
  :hover .column-controls {
    box-shadow: -4px 0px 4px 4px rgba(255, 255, 255, 0.75);
    background: rgba(255, 255, 255, 0.75);
  }
  :hover .column-actions-trigger {
    visibility: visible;
  }
  .column-actions-trigger:hover {
    color: ${globals.primary};
  }
`;

export const ColumnName = styled.div`
  cursor: pointer;
  padding: 4px;
  flex: 1 1 auto;
  :hover {
    color: ${globals.primary};
  }
  overflow: hidden;
  text-align: center;
`;

export const ColumnNameText = styled.span`
  width: 100%;
  height: 100%;
  text-align: center;
`;

export const IndexColumnVal = styled.div`
  width: 100%;
  height: 100%;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  :hover {
    color: ${globals.primary};
    background-color: #eee;
  }
`;

export const IndexColumnText = styled.div`
  text-align: center;
  flex: 1 1 auto;
  height: 20px;
  display: flex;
  align-content: space-around;
  justify-content: space-around;
  align-items: center;
  font-weight: 600;
`;

export const IndexColumnDrag = styled.div`
  flex: 0 0 auto;
  width: 100%;
  height: 2px;
  background-color: #eee;
  cursor: pointer;
  :hover {
    cursor: row-resize;
    background-color: rgb(51, 153, 255);
  }
  :highlight {
    position: absolute;
    background: rgb(51, 153, 255);
  }
`;

export const FilterIcon = styled(WBIcon)`
  cursor: pointer;
  color: ${globals.primary};
  :hover {
    background-color: #eee;
    border-radius: 2px;
  }
`;

export const ColumnAction = styled.div`
  cursor: pointer;
  padding: 5px 0px 0px 0px;
  flex: 0 0 auto;
  height: 100%;
  box-shadow: -4px 0px 4px 4px white;
  background: white;
  font-size: 20px;
`;

export const TableAction = styled.div<{highlight?: boolean}>`
  cursor: pointer;
  padding: 5px 4px 0px 9px;
  flex: 0 0 auto;
  height: 100%;
  width: 100%;
  color: ${props => (props.highlight ? 'white' : 'inherit')};
  background-color: ${props =>
    props.highlight ? 'rgb(3, 183, 206)' : 'inherit'};
  :hover {
    color: ${globals.primary};
    background-color: ${props =>
      props.highlight ? 'rgb(3, 183, 206)' : '#eee'};
  }
  box-shadow: #f8f8f8 -2px 0px 8px 4px;
`;

export const EllipsisIcon = styled(WBIcon)`
  width: 100%;
  height: 100%;
  padding-top: 4px;
`;

export const TableIcon = styled(WBIcon)<{highlight?: boolean}>`
  cursor: pointer;
  padding: 2px 0px 0px 0px;
  :hover {
    color: ${globals.primary};
    background-color: ${props =>
      props.highlight ? 'rgb(3, 183, 206)' : '#eee'};
    border-radius: 2px;
  }
`;

export const TableActionText = styled.span`
  cursor: pointer;
  margin-left: 10px;
  padding: 2px 0px 0px 0px;
  :hover {
    color: ${globals.primary};
    background-color: #eee;
    border-radius: 2px;
  }
`;

export const ControlIcon = styled(WBIcon)`
  cursor: pointer;
  color: ${globals.primary};
  margin: auto;
`;

export const SortIcon = styled(WBIcon)`
  cursor: pointer;
  color: #afafaf;
  :hover {
    background-color: #eee;
    border-radius: 2px;
  }
`;

export const ColumnEditorSection = styled.div`
  margin-bottom: 24px;
`;

export const ColumnEditorSectionLabel = styled.div`
  margin-bottom: 8px;
  font-weight: 600;
`;

export const ColumnEditorColumnName = styled.div`
  display: flex;
  align-items: center;
  color: ${globals.gray500};
`;

export const ColumnEditorFieldLabel = styled.div`
  margin-right: 8px;
`;

export const AssignmentWrapper = styled.div`
  display: flex;
  align-items: center;
`;

export const PanelNameEditor = styled.div`
  margin-bottom: 12px;
`;

export const PanelSettings = styled.div`
  padding: 8px 24px;
  background-color: #f6f6f6;
  border-radius: 4px;
  // min-width: 600px;
  :empty {
    padding: 0;
  }
  overflow: visible;
  // max-height: 300px;
`;

export const CellWrapper = styled.div`
  scrollbar-width: thin;
  overflow: auto;
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background-color: #eee;
  }
  width: 100%;
  height: 100%;
`;

export const CloseIconButton = styled(IconButton)`
  position: absolute;
  right: 8px;
  top: 12px;
`;
