import React from 'react';
import {useMemo} from 'react';
import * as Types from '@wandb/cg/browser/model/types';
import * as CGReact from '@wandb/common/cgreact';

import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';

type PanelMaybeProps = Panel2.PanelConverterProps;

const PanelMaybe: React.FC<PanelMaybeProps> = props => {
  const {input} = props;
  const nodeValueQuery = CGReact.useNodeValue(props.input);

  const nodeWithConvertedType = useMemo(() => {
    let convertedType = Spec.convert(input.type);
    if (convertedType == null) {
      // Hack to workaround the Weave Python not sending nullable
      // types correctly.
      // throw new Error('Invalid (null) panel input type');
      convertedType = input.type;
    }
    return {
      ...input,
      type: convertedType,
    };
  }, [input]);

  return nodeValueQuery.loading || nodeValueQuery.result == null ? (
    <div>-</div>
  ) : (
    <PanelComp2
      input={nodeWithConvertedType}
      inputType={nodeWithConvertedType.type}
      loading={props.loading}
      panelSpec={props.child}
      configMode={false}
      config={props.config}
      context={props.context}
      updateInput={props.updateInput}
      updateConfig={props.updateConfig}
      updateContext={props.updateContext}
    />
  );
};

export const Spec: Panel2.PanelConvertSpec = {
  id: 'maybe',
  displayName: 'Maybe',
  Component: PanelMaybe,
  convert: (inputType: Types.Type) => {
    let tags: Types.Type | undefined;
    if (Types.isTaggedValueLike(inputType)) {
      tags = Types.taggedValueTagType(inputType);
      inputType = Types.taggedValueValueType(inputType);
    }
    if (!Types.isUnion(inputType) || !Types.isAssignableTo('none', inputType)) {
      return null;
    }
    return Types.taggedValue(tags, Types.nonNullableDeep(inputType));
  },
  defaultFixedSize: childDims => childDims,
};
