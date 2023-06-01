import React from 'react';

import {ChildPanel} from './ChildPanel';
import * as Panel2 from './panel';

// import {useWeaveContext} from '../../context';
// import {useNodeWithServerType} from '../../react';
// import {usePanelContext} from './PanelContext';

const inputType = 'any' as const;
type PanelAutoProps = Panel2.PanelProps<typeof inputType>;

export const PanelAuto: React.FC<PanelAutoProps> = props => {
  // const weave = useWeaveContext();
  // const {stack} = usePanelContext();
  // const typedInputNode = useNodeWithServerType(props.input).result;
  // return (
  //   <div>
  //     Auto
  //     <div>{weave.typeToString(props.input.type, false)}</div>
  //     <div>{weave.expToString(props.input)}</div>
  //     <div>{weave.expToString(dereferenceAllVars(props.input, stack))}</div>
  //     {/* <div>{weave.typeToString(typedInputNode.type, false)}</div> */}
  //   </div>
  // );
  return (
    <ChildPanel
      config={props.input}
      updateConfig={props.updateConfig}
      updateConfig2={props.updateConfig2}
    />
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: false,
  id: 'Auto',
  Component: PanelAuto,
  inputType,
};
