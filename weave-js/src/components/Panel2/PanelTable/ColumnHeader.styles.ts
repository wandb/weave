import styled from 'styled-components';
import {WBIcon} from '../../../common/components/elements/WBIcon';

export const ColumnHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 8px;
  position: relative;
  min-height: 32px;
`;

export const ColumnName = styled.div`
  cursor: pointer;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0 8px;
`;

export const ColumnNameText = styled.span`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`;

export const ColumnAction = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
`;

export const ColumnActionContainer = styled.div`
  display: flex;
  align-items: center;
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
`;

export const ControlIcon = styled(WBIcon)`
  cursor: pointer;
  color: var(--gray-500);
  &:hover {
    color: var(--gray-700);
  }
`;

export const EllipsisIcon = styled(WBIcon)`
  cursor: pointer;
  color: var(--gray-500);
  &:hover {
    color: var(--gray-700);
  }
`;

export const ColumnEditorSection = styled.div`
  margin-bottom: 16px;
`;

export const ColumnEditorSectionLabel = styled.div`
  font-weight: 600;
  margin-bottom: 8px;
`;

export const AssignmentWrapper = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

export const ColumnEditorColumnName = styled.div`
  margin-top: 8px;
`;

export const ColumnEditorFieldLabel = styled.div`
  font-size: 12px;
  color: var(--gray-600);
  margin-bottom: 4px;
`;

export const PanelNameEditor = styled.div`
  width: 100%;
`;


export const PanelSettings = styled.div`
  margin-top: 16px;
`;
