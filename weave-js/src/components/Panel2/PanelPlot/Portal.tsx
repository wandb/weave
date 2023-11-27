import React, {useEffect, useRef} from 'react';
import ReactDOM from 'react-dom';

export const Portal: React.FC<{}> = props => {
  const ref = useRef(document.createElement('div'));
  useEffect(() => {
    const el = ref.current;
    document.body.appendChild(el);
    return () => {
      document.body.removeChild(el);
    };
  }, []);
  return ReactDOM.createPortal(props.children, ref.current);
};
