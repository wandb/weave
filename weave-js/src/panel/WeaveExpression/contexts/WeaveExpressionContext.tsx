import React, {
  createContext,
  FC,
  PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {useToggle} from '@wandb/weave/hookUtils';
import {withReact} from 'slate-react';
import {withHistory} from 'slate-history';
import {createEditor} from 'slate';
import {
  useWeaveDecorate,
  useWeaveExpressionState,
} from '@wandb/weave/panel/WeaveExpression/hooks';
import {WeaveExpressionProps} from '@wandb/weave/panel/WeaveExpression/types';
import {useWeaveContext} from '@wandb/weave/context';
import {ID} from '@wandb/weave/core';
import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
import classNames from 'classnames';

interface WeaveExpressionContextState {
  editor: any; // TODO: type this
  weaveExpressionState: ReturnType<typeof useWeaveExpressionState>;
  slateDecorator: ReturnType<typeof useWeaveDecorate>;
  isDocsPanelVisible: boolean;
  toggleIsDocsPanelVisible: (newVal?: boolean) => void;
}

const WeaveExpressionContext = createContext<
  WeaveExpressionContextState | undefined
>(undefined);
WeaveExpressionContext.displayName = 'PanelSearchInputContext';

// This creates and manages the Slate editor for the WeaveExpression component.
const useWeaveExpressionSlateEditor = () =>
  // {}: {
  // applyPendingExpr: any;
  // onChange: any;
  // }
  {
    // const {stack} = usePanelContext();

    const [editor] = useState(() =>
      withReact(withHistory(createEditor() as any))
    );
    const [editorId] = useState(ID());

    // Store the editor on the window, so we can modify its state
    // from automation.ts (test automation)
    useEffect(() => {
      window.weaveExpressionEditors[editorId] = {
        editor,
        applyPendingExpr: () => {},
        onChange: () => {},
        // TODO: re-enable these
        // applyPendingExpr,
        // onChange: (newValue: any) => onChange(newValue, stack),
      };
      return () => {
        delete window.weaveExpressionEditors[editorId];
      };
    }, [editor, editorId]);

    return useMemo(() => ({editor}), [editor]);
  };

export const WeaveExpressionContextProvider: FC<
  PropsWithChildren<WeaveExpressionProps>
> = ({children, ...props}) => {
  const weave = useWeaveContext();
  const weaveExpressionState = useWeaveExpressionState(props, editor, weave);
  const {applyPendingExpr, onChange, isValid, isTruncated} =
    weaveExpressionState;

  const {editor} = useWeaveExpressionSlateEditor();

  const slateDecorator = useWeaveDecorate(editor, weaveExpressionState.tsRoot);

  const [isDocsPanelVisible, toggleIsDocsPanelVisible] = useToggle(false);

  // these are the props passed to slate-react's <Editable> component
  const editableProps = useMemo(() => {
    return {
      className: classNames('weaveExpressionSlateEditable', {
        isValid,
        isTruncated,
      }),
      onKeyDownHandler,
      onBlur,
      onFocus,
      onCopy,
      slateDecorator,
      // spellCheck: false,
      // autoCorrect: false,
      // autoCapitalize: false,
      // autoComplete: 'off',
    };
  }, []);

  const contextState: WeaveExpressionContextState = useMemo(
    () => ({
      editor,
      slateDecorator,
      weaveExpressionState,
      isDocsPanelVisible,
      toggleIsDocsPanelVisible,
    }),
    [
      editor,
      isDocsPanelVisible,
      toggleIsDocsPanelVisible,
      weaveExpressionState,
      slateDecorator,
    ]
  );

  return (
    <WeaveExpressionContext.Provider value={contextState}>
      {children}
    </WeaveExpressionContext.Provider>
  );
};

export function useWeaveExpressionContext() {
  const context = useContext(WeaveExpressionContext);
  if (context == null) {
    throw new Error(
      `useWeaveExpressionContext called outside of WeaveExpressionContext.Provider`
    );
  }
  return context;
}
