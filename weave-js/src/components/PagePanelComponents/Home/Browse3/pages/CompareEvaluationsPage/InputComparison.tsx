import React from 'react';

import {parseRef} from '../../../../../../react';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {isRef} from '../common/util';

export const ICValueView: React.FC<{value: any}> = ({value}) => {
  let text = '';
  if (value == null) {
    return <NotApplicable />;
  } else if (typeof value === 'object') {
    text = JSON.stringify(value || {}, null, 2);
  } else if (typeof value === 'string' && isRef(value)) {
    return <SmallRef objRef={parseRef(value)} allowShrink />;
  } else {
    text = value.toString();
  }

  text = trimWhitespace(text);

  return (
    <pre
      style={{
        whiteSpace: 'pre-wrap',
        textAlign: 'left',
        wordBreak: 'break-all',
      }}>
      {text}
    </pre>
  );
};

const trimWhitespace = (str: string) => {
  // Trim leading and trailing whitespace
  return str.replace(/^\s+|\s+$/g, '');
};
