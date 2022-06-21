import React from 'react';
import * as Types from '@wandb/cg/browser/model/types';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import * as Op from '@wandb/cg/browser/ops';

type PanelWBObjectProps = Panel2.PanelConverterProps;

const PanelWBObject: React.FC<PanelWBObjectProps> = props => {
  const mediaNode = Op.opFileMedia({file: props.input});
  const convertedType = Spec.convert(props.inputType);
  if (convertedType == null) {
    throw new Error('Invalid (null) PanelWBObject input type');
  }
  return (
    <PanelComp2
      inputType={convertedType}
      input={mediaNode}
      loading={props.loading}
      panelSpec={props.child}
      configMode={false}
      config={props.config}
      context={props.context}
      updateConfig={props.updateConfig}
      updateContext={props.updateContext}
    />
  );
};

export const Spec: Panel2.PanelConvertSpec = {
  id: 'object-file',
  Component: PanelWBObject,
  convert: (inputType: Types.Type) => {
    if (!Types.isFileLike(inputType)) {
      return null;
    }
    return Types.fileWbObjectType(inputType) ?? null;
  },
};
