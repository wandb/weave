import {Popup} from 'semantic-ui-react';
import styled from 'styled-components';
import {Colors, hexToRGB} from '../common/css/globals.styles';

export const Tooltip = styled(Popup).attrs({
  basic: true, // This removes the pointing arrow.
  mouseEnterDelay: 500,
  popperModifiers: {
    preventOverflow: {
      // Prevent popper from erroneously constraining the popup.
      // Without this, tooltips in single row table cells get positioned under the cursor,
      // causing them to immediately close.
      boundariesElement: 'viewport',
    },
  },
})`
  && {
    color: ${Colors.WHITE};
    background: ${Colors.GRAY_800};
    border-color: ${Colors.GRAY_700};
    box-shadow: 0px 4px 6px ${hexToRGB(Colors.BLACK, 0.2)};
    font-size: 14px;
    line-height: 140%;
    max-width: 300px;
  }
`;
