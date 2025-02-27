import {usePanelContext} from '../../components/Panel2/PanelContext';
import {
  constNodeUnsafe,
  constString,
  isVoidNode,
  Node,
  opPick,
  opRunId,
  opRunName,
} from '../../core';
import {useNodeValue} from '../../react';

export const useRunName = (runNode: Node | null) => {
  const {frame} = usePanelContext();

  const emptyObject = constNodeUnsafe({type: 'dict', objectType: 'any'}, {});

  const customRunNamesNode =
    runNode != null && frame.customRunNames != null
      ? opPick({
          obj: isVoidNode(frame.customRunNames)
            ? emptyObject
            : frame.customRunNames,
          key: opRunId({run: runNode}),
        })
      : constString('');

  const displayNameNode =
    runNode != null ? opRunName({run: runNode}) : constString('');

  const customRunNameValue = useNodeValue(customRunNamesNode);
  const displayNameValue = useNodeValue(displayNameNode);

  return customRunNameValue.result ?? displayNameValue.result ?? '';
};
