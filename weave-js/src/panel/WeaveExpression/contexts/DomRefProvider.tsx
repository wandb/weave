import {FC, MutableRefObject, useMemo, useRef} from 'react';
import {
  GenericProvider,
  useGenericContext,
} from '@wandb/weave/panel/WeaveExpression/contexts/GenericProvider';
import {Button} from 'semantic-ui-react';

interface DomRefProviderOutput {
  expressionEditorDomRef: MutableRefObject<HTMLDivElement | null>;
  runButtonDomRef: MutableRefObject<Button | null>;
}

export const DomRefProvider: FC = ({children}) => {
  const expressionEditorDomRef = useRef<HTMLDivElement | null>(null);
  const runButtonDomRef = useRef<Button | null>(null);
  const domRefProviderOutput: DomRefProviderOutput = useMemo(
    () => ({expressionEditorDomRef, runButtonDomRef}),
    []
  );
  return (
    <GenericProvider<DomRefProviderOutput>
      value={domRefProviderOutput}
      displayName="DomRefContext">
      {children}
    </GenericProvider>
  );
};

export const useDomRefContext = () =>
  useGenericContext<DomRefProviderOutput>({displayName: 'DomRefContext'});
