import {getTableKeysFromNodeType} from '@wandb/weave/common/util/table';
import {useWeaveContext} from '@wandb/weave/context';
import {
  constString,
  EditingNode,
  opPick,
  Stack,
  varNode,
} from '@wandb/weave/core';
import {
  IDENTIFER_COLOR,
  OPERATOR_COLOR,
} from '@wandb/weave/panel/WeaveExpression/styles';
import React, {useEffect, useState} from 'react';
import {Dropdown, DropdownProps} from 'semantic-ui-react';

import {Icon, IconNames} from '../../Icon';
import {makeEventRecorder} from '../panellib/libanalytics';
import * as S from './EmptyExpressionPanel.styles';
import {runSummary} from './shortcutExpressions';
import {REGULAR_TEXT_COLOR} from './util';

const recordEvent = makeEventRecorder('EmptyPanelShortcut');

interface PickCardProps {
  updateExp: (newExp: EditingNode) => void;
  stack: Stack;
}

export const PickCard: React.FC<PickCardProps> = ({updateExp, stack}) => {
  const [tableKeys, setTableKeys] = useState<string[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const weave = useWeaveContext();

  useEffect(() => {
    const fetchTableKeys = async () => {
      const runsValFromStack = stack.find(s => s.name === 'runs');
      if (!runsValFromStack) {
        return;
      }

      try {
        const refined = await weave.refineNode(
          runSummary(varNode(runsValFromStack.value.type, 'runs')),
          stack
        );

        const {tableKeys: keys} = getTableKeysFromNodeType(refined.type);
        setTableKeys(keys.filter(k => k !== ''));
      } catch (error) {
        setTableKeys([]);
      }
    };

    fetchTableKeys();
  }, [stack, weave]);

  const handleKeySelect = (newKey: string) => {
    if (newKey !== selectedKey) {
      setSelectedKey(newKey);
      handleKeyAction(newKey);
    }
  };

  const handleKeyAction = async (key: string) => {
    const runsValFromStack = stack.find(s => s.name === 'runs');
    if (!runsValFromStack) {
      return;
    }

    const inputNode = varNode(runsValFromStack.value.type, 'runs');

    const res = await weave.refineNode(runSummary(inputNode), stack);

    const keyAccessNode = opPick({
      obj: res,
      key: constString(key),
    });

    await weave.refineEditingNode(keyAccessNode, stack);
    updateExp(keyAccessNode);

    recordEvent('RUN_TABLE');
  };

  const dropdownOptions = tableKeys.map(key => ({
    key,
    text: key,
    value: key,
  }));

  return (
    <S.Card
      role="button"
      aria-label="View logged table"
      onClick={() => setDropdownOpen(true)}
      onMouseLeave={() => setDropdownOpen(false)}>
      <S.CardTitleContainer>
        <S.CardIcon name={IconNames.Table} />
        <S.CardTitle>View logged table</S.CardTitle>
      </S.CardTitleContainer>
      <S.CardSubtitle>
        <S.ExpressionWrapper className="pickcard-expression">
          <span style={{color: IDENTIFER_COLOR}}>runs</span>
          <span style={{color: REGULAR_TEXT_COLOR}}>.</span>
          <span style={{color: OPERATOR_COLOR}}>summary</span>
          <S.BracketGroup>
            <span style={{padding: 0, margin: 0}}>["</span>
            <S.StyledDropdownWrapper>
              <Dropdown
                className="ui dropdown"
                options={dropdownOptions}
                search
                selection
                compact
                scrolling
                value={selectedKey}
                text="<key>"
                noResultsMessage="No tables found"
                onChange={(e: React.SyntheticEvent, data: DropdownProps) => {
                  handleKeySelect(data.value as string);
                }}
                onOpen={() => setDropdownOpen(true)}
                onClose={() => setDropdownOpen(false)}
                selectOnNavigation={false}
                open={dropdownOpen}
                onClick={e => {
                  e.stopPropagation();
                  setDropdownOpen(true);
                }}
                selectOnBlur={false}
                closeOnBlur
                closeOnEscape
              />
            </S.StyledDropdownWrapper>
            <span style={{padding: 0, margin: 0}}>"]</span>
          </S.BracketGroup>
        </S.ExpressionWrapper>
      </S.CardSubtitle>
    </S.Card>
  );
};
