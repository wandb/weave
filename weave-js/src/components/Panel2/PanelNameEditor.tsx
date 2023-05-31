import {WBMenuOption} from '@wandb/ui';
import WBSuggester, {
  WBSuggesterOptionFetcher,
} from '@wandb/weave/common/components/elements/WBSuggester';
import React from 'react';

import {InlineContentEditable, PanelNameSpan} from './Editor.styles';

interface PanelNameEditorProps {
  value: string;
  disabled?: boolean;
  autocompleteOptions?: WBMenuOption[] | WBSuggesterOptionFetcher;
  setValue(val: string): void;
}

const PanelNameEditor: React.FC<PanelNameEditorProps> = props => {
  const ref = React.useRef<HTMLSpanElement>(null);
  // Disabled, we just always show all options
  // const [autocompleterQuery, setAutocompleterQuery] = React.useState('');
  const [autocompleterOpen, setAutocompleterOpen] = React.useState(false);
  return (
    <>
      <PanelNameSpan data-test-comp="PanelNameEditor" spellCheck="false">
        <WBSuggester
          options={props.autocompleteOptions}
          onSelect={v => {
            setAutocompleterOpen(false);
            props.setValue(v as string);
          }}
          // Disabled, we just always show all options
          query={''}
          open={autocompleterOpen}
          onParentScroll={() => setAutocompleterOpen(false)}>
          {({inputRef}) => (
            <InlineContentEditable
              innerRef={node => {
                (ref as any).current = node;
                inputRef(node);
              }}
              value={props.value}
              disabled={props.disabled}
              onFocus={() => {
                setAutocompleterOpen(true);
                // setAutocompleterQuery(props.value);
              }}
              onBlur={() => setAutocompleterOpen(false)}
              onTempChange={v => {
                // setAutocompleterQuery(v);
                setAutocompleterOpen(true);
              }}
              onChange={v => {}}
            />
          )}
        </WBSuggester>
      </PanelNameSpan>
    </>
  );
};

export default PanelNameEditor;
