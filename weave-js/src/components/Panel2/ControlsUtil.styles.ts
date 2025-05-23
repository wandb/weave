import styled from 'styled-components';
import {GLOBAL_COLORS} from '../../common/util/colors';

export const InputWrapper = styled.div`
  font-size: 13px;
  .ui.input {
    color: ${GLOBAL_COLORS.gray.toString()};
    > input {
      border: 0;
      background: transparent;
      color: $darkGray;
      &::-webkit-input-placeholder {
        color: ${GLOBAL_COLORS.gray.toString()};
      }
    }
    > i.icon {
      opacity: 1;
    }
  }
`;
