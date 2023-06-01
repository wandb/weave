import {foundations} from '@wandb/ui';
import styled, {css} from 'styled-components';

import AutoCompletingInput from './AutoCompletingInput';

const {legacy} = foundations;

export const CaretWrapper = styled.div`
  width: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-around;
  border-left: 1px solid transparent;
  position: relative;
  z-index: 0;
  &:hover {
    background: #e9e9e9 !important;
  }
`;

export const TypeableWrapper = styled.div<{
  open: boolean;
  inputFocused: boolean;
}>`
  border: 1px solid transparent;
  border-radius: 2px;
  width: 140px;
  display: flex;
  align-items: stretch;
  cursor: pointer;
  .wbic-ic-next {
    color: transparent;
    transform: rotate(90deg);
  }
  ${props =>
    props.inputFocused &&
    css`
      .wbic-ic-next {
        color: black;
      }
    `}
  ${props =>
    !props.inputFocused &&
    css`
      &:hover {
        border: 1px solid ${legacy.border};
        ${CaretWrapper} {
          background: #f1f1f1;
          border-left: 1px solid ${legacy.border};
        }
        .wbic-ic-next {
          color: black;
        }
      }
    `}
`;

export const BasicWrapper = styled.div<{open: boolean}>`
  border: 1px solid transparent;
  border-radius: 2px;
  width: calc(100% + 12px);
  max-width: 140px;
  padding: 2px 6px;
  display: flex;
  align-items: center;
  cursor: pointer;
  outline: none;
  .wbic-ic-next {
    transform: rotate(90deg);
  }
  &:hover {
    .wbic-ic-next {
      color: black;
    }
  }
`;

export const DisplayedValue = styled.span`
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
`;

export const StyledAutoCompletingInput = styled(AutoCompletingInput)`
  position: relative;
  z-index: 1;
`;

export const DropdownArrow = styled.div`
  border-top: 0.25em solid ${legacy.textPrimary};
  border-left: 0.25em solid transparent;
  border-right: 0.25em solid transparent;
  position: relative;
  top: 0.1em;
  margin-left: 0.2em;
`;
