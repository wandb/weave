import * as globals from '@wandb/weave/common/css/globals.styles';
import styled from 'styled-components';

import {OBLIVION} from '../../common/css/color.styles';
import {hexToRGB} from '../../common/css/utils';
import {Icon} from '../Icon';

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
  :hover .column-actions-trigger {
    visibility: visible;
  }
  .column-actions-trigger:hover {
    color: ${globals.primary};
  }
`;
ColumnHeader.displayName = 'S.ColumnHeader';

export const ColumnName = styled.div`
  cursor: pointer;
  padding: 4px 4px 4px 1em;
  flex: 1 1 auto;
  :hover {
    color: ${globals.primary};
  }
  overflow: hidden;
`;
ColumnName.displayName = 'S.ColumnName';

export const ColumnNameText = styled.span`
  width: 100%;
  height: 100%;
  text-align: center;
`;
ColumnNameText.displayName = 'S.ColumnNameText';

export const IndexColumnVal = styled.div`
  width: 100%;
  height: 100%;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 0 8px;
  :hover {
    color: ${globals.primary};
    background-color: ${hexToRGB(OBLIVION, 0.04)};
  }
`;
IndexColumnVal.displayName = 'S.IndexColumnVal';

export const IndexColumnText = styled.div`
  text-align: center;
  flex: 1 1 auto;
  height: 20px;
  display: flex;
  align-content: space-around;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
`;
IndexColumnText.displayName = 'S.IndexColumnText';

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
IndexColumnDrag.displayName = 'S.IndexColumnDrag';

export const FilterIcon: typeof Icon = styled(Icon)`
  cursor: pointer;
  color: ${globals.primary};
  :hover {
    background-color: #eee;
    border-radius: 2px;
  }
`;

export const ColumnAction = styled.div<{isHovered?: boolean}>`
  cursor: pointer;
  height: 100%;
  background-color: transparent;
`;
ColumnAction.displayName = 'S.ColumnAction';

export const ColumnActionContainer = styled.div<{isHovered?: boolean}>`
  display: flex;
  padding: 5px 0px 0px 0px;
  font-size: 20px;
  flex: 0 0 auto;
  height: 100%;

  :hover {
    background-color: ${hexToRGB(OBLIVION, 0.04)};
  }
`;
ColumnActionContainer.displayName = 'S.ColumnActionContainer';

export const TableAction = styled.div<{
  highlight?: boolean;
}>`
  cursor: pointer;
  padding: 5px 4px 0px 4px;
  flex: 0 0 auto;
  height: 100%;
  width: 100%;
  color: ${props => (props.highlight ? 'white' : 'inherit')};
  background-color: ${props =>
    props.highlight ? 'rgb(3, 183, 206)' : 'inherit'};
  :hover {
    color: ${globals.primary};
    background-color: ${props =>
      props.highlight ? 'rgb(3, 183, 206)' : hexToRGB(OBLIVION, 0.04)};
  }
  box-shadow: #f8f8f8 -2px 0px 8px 4px;
  display: inline-flex;
  justify-content: center;
`;
TableAction.displayName = 'S.TableAction';

export const TableIcon: typeof Icon = styled(Icon)<{highlight?: boolean}>`
  cursor: pointer;
  padding: 2px 0px 0px 0px;
  :hover {
    color: ${globals.primary};
    background-color: ${props =>
      props.highlight ? 'rgb(3, 183, 206)' : '#eee'};
    border-radius: 2px;
  }
`;

export const ControlIcon: typeof Icon = styled(Icon)`
  cursor: pointer;
  color: ${globals.primary};
  margin: auto;
`;

export const SortIcon: typeof Icon = styled(Icon)`
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
ColumnEditorSection.displayName = 'S.ColumnEditorSection';

export const ColumnEditorSectionLabel = styled.div`
  margin-bottom: 8px;
  font-weight: 600;
`;
ColumnEditorSectionLabel.displayName = 'S.ColumnEditorSectionLabel';

export const ColumnEditorColumnName = styled.div`
  display: flex;
  align-items: center;
  color: ${globals.gray500};
`;
ColumnEditorColumnName.displayName = 'S.ColumnEditorColumnName';

export const ColumnEditorFieldLabel = styled.div`
  margin-right: 8px;
`;
ColumnEditorFieldLabel.displayName = 'S.ColumnEditorFieldLabel';

export const AssignmentWrapper = styled.div`
  display: flex;
  align-items: center;
`;
AssignmentWrapper.displayName = 'S.AssignmentWrapper';

export const PanelNameEditor = styled.div`
  margin-bottom: 12px;
`;
PanelNameEditor.displayName = 'S.PanelNameEditor';

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
PanelSettings.displayName = 'S.PanelSettings';

export const CellWrapper = styled.div`
  width: 100%;
  height: 100%;
  :hover {
    background-color: ${hexToRGB(OBLIVION, 0.04)};
  }
`;
CellWrapper.displayName = 'S.CellWrapper';

export const IndexCellCheckboxWrapper = styled.div<{isSelected: boolean}>`
  ${({isSelected}) => (isSelected ? '' : 'visibility: hidden;')}
  margin-right: 8px;
`;
IndexCellCheckboxWrapper.displayName = 'S.IndexCellCheckboxWrapper';
