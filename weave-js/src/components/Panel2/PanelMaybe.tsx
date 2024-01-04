import {
  isAssignableTo,
  isTaggedValueLike,
  isUnion,
  Node,
  nonNullableDeep,
  taggedValue,
  taggedValueTagType,
  taggedValueValueType,
  Type,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import {NullResult} from '../../react';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import {PanelContextProvider} from './PanelContext';

type PanelMaybeProps = Panel2.PanelConverterProps;

interface NullResultErrorBoundaryProps {
  onErrorCapture?: () => void;
  children?: React.ReactNode;
}

interface NullResultErrorBoundaryState {
  isNullValue: boolean;
}

// Special error boundary for panel maybe. This allows us to render
// child panels without the child panel needing to handle null values.
// useNodeValue will throw a NullResult error if the node value is null
// inside of PanelMaybe.
class NullResultErrorBoundary extends React.Component<
  NullResultErrorBoundaryProps,
  NullResultErrorBoundaryState
> {
  public static getDerivedStateFromError(
    error: NullResult | Error
  ): NullResultErrorBoundaryState {
    if (error instanceof NullResult) {
      return {isNullValue: true};
    } else {
      return {isNullValue: false};
    }
  }

  public state: NullResultErrorBoundaryState = {
    isNullValue: false,
  };

  componentDidCatch(error: NullResult | Error, info: React.ErrorInfo) {
    if (error instanceof NullResult) {
      this.setState({isNullValue: true});
      this.props.onErrorCapture?.();
    } else {
      throw error;
    }
  }

  public render() {
    if (this.state.isNullValue) {
      return (
        <div
          style={{
            width: '100%',
            height: '100%',
            overflowX: 'hidden',
            overflowY: 'auto',
            margin: 'auto',
            textAlign: 'center',
            wordBreak: 'normal',
            display: 'flex',
            flexDirection: 'column',
            alignContent: 'space-around',
            justifyContent: 'space-around',
            alignItems: 'center',
          }}>
          -
        </div>
      );
    }

    return this.props.children;
  }
}

const useLatchingState = <T extends any>(currentValue: T) => {
  // This hook is used to latch the value of a state variable. The first value
  // is set immediately and does not change until openLatch is called. After
  // openLatch is called, the value will not update immediately, but will
  // update on the next render. (I am calling this "latching" the value). I am
  // not sure if this is useful elsewhere, but it is useful for PanelMaybe. In
  // particular, we use this to refresh the error boundary by calling
  // openLatch. This waits for the next time the value changes, and then
  // updates the error boundary.

  const [value, setValue] = React.useState(currentValue);
  const [latchClosed, setLatchClosed] = React.useState(true);
  const [valueAtUnlatch, setValueAtUnlatch] = React.useState(currentValue);

  const openLatch = React.useCallback(() => {
    setValueAtUnlatch(currentValue);
    setLatchClosed(false);
  }, [currentValue]);

  React.useEffect(() => {
    if (
      !latchClosed &&
      currentValue !== valueAtUnlatch &&
      currentValue !== value
    ) {
      setValue(currentValue);
      setLatchClosed(true);
    }
  }, [currentValue, latchClosed, setValue, value, valueAtUnlatch]);

  return {value, openLatch};
};

const useIdFromDeps = (deps: any[]) => {
  return useMemo(() => {
    return Math.random();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
};

const PanelMaybe: React.FC<PanelMaybeProps> = props => {
  const {input} = props;

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

  return (
    <MaybeWrapper
      node={nodeWithConvertedType}
      deps={[
        nodeWithConvertedType,
        props.child,
        props.config,
        props.context,
        props.loading,
        props.updateConfig,
        props.updateContext,
        props.updateInput,
      ]}>
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
    </MaybeWrapper>
  );
};

export const MaybeWrapper: React.FC<{node: Node; deps?: any[]}> = props => {
  // We always render our child, so that its useNodeValue calls can be merged
  // with other active components. Ie, we don't want to waterfall here.

  // NullResultErrorBoundary and useNodeValue work together to prevent
  // children from rendering if the node value is null. Therefore child
  // panels do not need to handle null values!

  const {value: boundaryKey, openLatch} = useLatchingState(
    useIdFromDeps(props.deps ?? [])
  );

  return (
    <PanelContextProvider panelMaybeNode={props.node}>
      <NullResultErrorBoundary key={boundaryKey} onErrorCapture={openLatch}>
        {props.children}
      </NullResultErrorBoundary>
    </PanelContextProvider>
  );
};

export const Spec: Panel2.PanelConvertSpec = {
  id: 'maybe',
  displayName: 'Maybe',
  Component: PanelMaybe,
  convert: (inputType: Type) => {
    let tags: Type | undefined;
    if (isTaggedValueLike(inputType)) {
      tags = taggedValueTagType(inputType);
      inputType = taggedValueValueType(inputType);
    }
    if (!isUnion(inputType) || !isAssignableTo('none', inputType)) {
      return null;
    }
    return taggedValue(tags, nonNullableDeep(inputType));
  },
  defaultFixedSize: childDims => childDims,
};
