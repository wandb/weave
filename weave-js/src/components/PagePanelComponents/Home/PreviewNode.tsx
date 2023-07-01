import * as w from '@wandb/weave/core';
import {useConfig} from '../../Panel2/panel';
import {ChildPanel} from '../../Panel2/ChildPanel';

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
  inputNode: w.Node;
}> = props => {
  const [childConfig, updateConfig] = useConfig({
    id: '',
    input_node: props.inputNode,
  });

  return (
    <div
      style={{
        width: '100%',
        height: '200px',
        border: '2px solid #DADEE3',
        borderRadius: '6px',
      }}>
      <Unclickable
        style={{
          backgroundColor: '#d2d2d21a',
        }}>
        <Scaler scale={0.4}>
          <ChildPanel
            config={childConfig as any}
            updateConfig={updateConfig as any}
          />
        </Scaler>
      </Unclickable>
    </div>
  );
};
