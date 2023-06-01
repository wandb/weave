import React from 'react';
import ReactDOM from 'react-dom';

import * as S from './SidebarPopout.styles';

interface SidebarPopoutProps {
  className?: string;
  anchor: HTMLElement;
  onPopoutChange?: (node: HTMLElement | null) => void;
}
const SidebarPopout: React.FC<SidebarPopoutProps> = props => {
  // coordinates are from top-right origin, because inspector is on the right
  const [position, setPosition] = React.useState<{
    x: number;
    y: number;
  } | null>(null);
  React.useEffect(() => {
    const anchorRect = props.anchor.getBoundingClientRect();
    setPosition({x: 280, y: anchorRect.top});
  }, [props.anchor]);

  if (!position) {
    return <></>;
  }
  return ReactDOM.createPortal(
    <S.Wrapper
      className={props.className}
      onClick={e => e.stopPropagation()}
      position={position}
      ref={node => {
        props.onPopoutChange?.(node);
      }}>
      {props.children}
    </S.Wrapper>,
    document.body
  );
};

export default SidebarPopout;
