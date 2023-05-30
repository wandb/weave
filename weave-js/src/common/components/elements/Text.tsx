// import classnames from 'classnames';
import classNames from 'classnames';
import React from 'react';

import {NameProps, pickNameProps} from '../../util/reactUtils';

interface TextProps {
  children: any;
  maxWidth?: number;
  as?: any;
  alignSelf?: string;
}

const singleLineTextClass = 'text__single-line';

// Renders text
// If the text is given a maxSize prop it will
// overflow with no line wrap and ellipsis.
export const SingleLineText: React.SFC<TextProps & NameProps> = props => {
  const passThrough = pickNameProps(props);
  const className = classNames(props.className, singleLineTextClass);
  const style = {
    maxWidth: props.maxWidth ? props.maxWidth : '',
    alignSelf: props.alignSelf ? props.alignSelf : '',
  };
  const title = Array.isArray(props.children)
    ? props.children.join('')
    : props.children;
  const otherProps = {className, style, title};

  const El = props.as || 'span';

  return (
    <El {...passThrough} {...otherProps}>
      {props.children}
    </El>
  );
};
