import {
  fileWbObjectType,
  isFileLike,
  opFileMedia,
  Type,
} from '@wandb/weave/core';
import React from 'react';

import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';

type PanelWBObjectProps = Panel2.PanelConverterProps;

const PanelWBObject: React.FC<PanelWBObjectProps> = props => {
  const mediaNode = opFileMedia({file: props.input});
  const convertedType = Spec.convert(props.inputType ?? props.input.type);
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
  convert: (inputType: Type) => {
    if (!isFileLike(inputType)) {
      return null;
    }
    return fileWbObjectType(inputType) ?? null;
  },
};
