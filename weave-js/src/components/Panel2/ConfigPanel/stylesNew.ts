import * as globals from '@wandb/weave/common/css/globals.styles';
import styled, {css} from 'styled-components';

export const PostfixContainerWrap = styled.div`
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
`;
PostfixContainerWrap.displayName = 'S.PostfixContainerWrap';

export const PostfixContainer = styled.div`
  display: flex;
`;
PostfixContainer.displayName = 'S.PostfixContainer';

export const ConfigOptionLabel = styled.div`
  width: 92px;
  margin-right: 8px;
  flex-shrink: 0;
  color: ${globals.GRAY_500};
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;
ConfigOptionLabel.displayName = 'S.ConfigOptionLabel';

export const ConfigOptionActions = styled.div`
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  align-items: center;
`;
ConfigOptionActions.displayName = 'S.ConfigOptionActions';

export const ConfigOptionField = styled.div`
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
`;
ConfigOptionField.displayName = 'S.ConfigOptionField';

export const ConfigOption = styled.div<{multiline: boolean}>`
  position: relative;
  margin: ${p => (p.multiline ? 6 : 2)}px 0;
  min-height: 28px;
  display: flex;
  ${p =>
    !p.multiline
      ? css`
          align-items: center;
        `
      : css`
          flex-direction: column;
        `}

  &:not(:hover) ${ConfigOptionActions} {
    display: none;
  }
`;
ConfigOption.displayName = 'S.ConfigOption';
