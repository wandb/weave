import React from 'react';

const LinkButton: React.FC<React.HTMLProps<HTMLSpanElement>> = props => {
  return (
    <span
      tabIndex={0}
      role="button"
      {...props}
      className={'link-button ' + props.className || ''}></span>
  );
};

export default LinkButton;
