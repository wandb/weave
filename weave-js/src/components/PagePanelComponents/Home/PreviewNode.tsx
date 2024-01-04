import {MOON_250} from '@wandb/weave/common/css/color.styles';
import React, {useMemo} from 'react';

import {urlPrefixed} from '../../../config';

export const Scaler: React.FC<{
  scale: number;
  children: React.ReactNode;
}> = props => {
  const scale = Math.max(Math.min(props.scale, 1), 0);
  const upsize = 100.0 / scale;
  const offset = (100.0 * (1.0 - scale)) / 2.0;
  return (
    <div
      style={{
        width: `${upsize}%`,
        height: `${upsize}%`,
        translate: `-${offset}% -${offset}%`,
        scale: `${scale}`,
      }}>
      <div
        style={{
          width: '100%',
          height: '100%',
        }}>
        {props.children}
      </div>
    </div>
  );
};

export const Unclickable: React.FC<{
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = props => {
  return (
    <div
      style={{
        height: '100%',
        width: '100%',
        position: 'relative',
      }}
      onClick={e => {
        e.preventDefault();
        e.stopPropagation();
      }}>
      <div
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
          zIndex: 999,
          ...(props.style ?? {}),
        }}
        onClick={e => {
          e.preventDefault();
          e.stopPropagation();
        }}
      />
      {props.children}
    </div>
  );
};

export const PreviewNode: React.FC<{
  inputExpr: string;
}> = props => {
  const url = useMemo(() => {
    return urlPrefixed(
      `/?previewMode=true&exp=${encodeURIComponent(props.inputExpr)}`,
      true
    );
  }, [props.inputExpr]);

  return (
    <div
      style={{
        width: '100%',
        height: '200px',
        border: `2px solid ${MOON_250}`,
        borderRadius: '6px',
        overflow: 'hidden',
      }}>
      <Unclickable
        style={{
          backgroundColor: '#d2d2d21a',
        }}>
        <Scaler scale={0.4}>
          <iframe
            title="Asset Preview"
            src={url}
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
            }}
          />
        </Scaler>
      </Unclickable>
    </div>
  );
};
