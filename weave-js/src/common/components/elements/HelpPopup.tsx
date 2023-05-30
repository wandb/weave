import React from 'react';
import {Icon, Popup} from 'semantic-ui-react';

import {TargetBlank} from '../../util/links';

interface HelpPopupProps {
  helpText: string;
  docUrl?: string;
}

const HelpPopup: React.FC<HelpPopupProps> = props => {
  const popup = (
    <Popup
      inverted
      size="mini"
      className="help-popup-content"
      trigger={<Icon name="help circle" size="small" />}
      content={props.helpText}
    />
  );
  const returnVal =
    props.docUrl != null ? (
      <TargetBlank href={props.docUrl}>{popup}</TargetBlank>
    ) : (
      popup
    );
  return <span className="help-popup">{returnVal}</span>;
};

export default HelpPopup;
