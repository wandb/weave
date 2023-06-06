import React, {JSX} from 'react';
import {Icon, Popup, PopupProps} from 'semantic-ui-react';
import * as globals from '@wandb/weave/common/css/globals.styles';

import {TargetBlank} from '../../util/links';
import styled from 'styled-components';

const HelpPopupSpan = styled.span({
  cursor: 'help',
  color: globals.GRAY_500,
  fontWeight: 400,
  '&:hover': {
    color: globals.GRAY_700,
  },
});
HelpPopupSpan.displayName = 'HelpPopupSpan';

const HelpPopupUnderline = styled.div({
  textDecoration: 'underline',
  textDecorationStyle: 'dotted',
});
HelpPopupUnderline.displayName = 'HelpPopupSpan';

interface HelpPopupProps {
  helpText: string; // the text to display in the popup
  trigger?: JSX.Element | string; // if present, the help popup will be triggered by this text instead of the help icon
  docUrl?: string; // if present, clicking the help popup will open this url in a new tab
  popupPosition?: PopupProps['position'];
}

const HelpPopup: React.FC<HelpPopupProps> = props => {
  const {helpText, docUrl, trigger, popupPosition} = props;
  const triggerElement =
    trigger == null ? (
      <Icon name="help circle" size="small" />
    ) : typeof trigger === 'string' ? (
      <HelpPopupUnderline>
        <HelpPopupSpan>{trigger}</HelpPopupSpan>
      </HelpPopupUnderline>
    ) : (
      <HelpPopupUnderline>{trigger}</HelpPopupUnderline>
    );
  const popup = (
    <Popup
      basic
      popperModifiers={{
        preventOverflow: {
          boundariesElement: 'offsetParent',
        },
      }}
      inverted
      size="mini"
      className="help-popup-content"
      trigger={triggerElement}
      content={helpText}
      position={popupPosition}
      pinned={popupPosition != null}
    />
  );
  const returnVal =
    docUrl != null ? <TargetBlank href={docUrl}>{popup}</TargetBlank> : popup;
  return <span className="help-popup">{returnVal}</span>;
};

export default HelpPopup;
