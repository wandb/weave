import Markdown from '@wandb/weave/common/components/Markdown';
import * as globalStyles from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {constString, maybe, Node, NodeOrVoidNode} from '@wandb/weave/core';
import * as Diff from 'diff';
import React, {useContext} from 'react';

import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import * as S from './PanelString.styles';
import {TooltipTrigger} from './Tooltip';
import {WeaveFormatContext} from './WeaveFormatContext';

const rtlChars =
  /[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/;

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    'string' as const,
    'number' as const,
    'boolean' as const,
    'id' as const,
    {type: 'WandbArtifactRef' as const},
  ],
};

interface PanelStringConfigState {
  mode: 'plaintext' | 'markdown' | 'diff';

  // Diff only: expression to compare against
  diffComparand?: Node;
  diffMode?: 'chars' | 'words' | 'lines';
}

type PanelStringProps = Panel2.PanelProps<
  typeof inputType,
  PanelStringConfigState
>;

const MAX_DISPLAY_LENGTH = 100;

function isURL(text: string): boolean {
  try {
    const url = new URL(text);
    if (url && (url.protocol === 'http:' || url.protocol === 'https:')) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/**
 * Determines if a given text contains any right-to-left (RTL) script characters.
 *
 * RTL script characters are defined as any character within the Unicode ranges:
 * - U+0590 to U+05FF
 * - U+0600 to U+06FF
 * - U+0750 to U+077F
 * - U+08A0 to U+08FF
 * - U+FB50 to U+FDFF
 * - U+FE70 to U+FEFF
 * Matching arabic, hebrew, and other related scripts.
 *
 * @param text - The text to be checked for RTL characters.
 * @returns `true` if the text contains RTL characters, otherwise `false`.
 */
const isRTL = (text: string): boolean => {
  return rtlChars.test(text);
};

const defaultConfig = (): PanelStringConfigState => {
  return {
    mode: 'plaintext',
  };
};

const defaultComparand = constString('');

export const PanelStringConfig: React.FC<PanelStringProps> = props => {
  const config = props.config ?? defaultConfig();
  const updateConfig = props.updateConfig;

  const weave = useWeaveContext();

  const setMode = React.useCallback(
    (mode: PanelStringConfigState['mode']) => {
      updateConfig({...config, mode});
    },
    [config, updateConfig]
  );
  const setComparand = React.useCallback(
    (expr: NodeOrVoidNode) => {
      if (!weave.typeIsAssignableTo(expr.type, maybe('string'))) {
        return;
      }

      updateConfig({...config, diffComparand: expr as Node});
    },
    [config, updateConfig, weave]
  );
  const setDiffMode = React.useCallback(
    (diffMode: PanelStringConfigState['diffMode']) => {
      updateConfig({...config, diffMode});
    },
    [config, updateConfig]
  );

  return (
    <>
      <ConfigPanel.ConfigOption label="Mode">
        <ConfigPanel.ModifiedDropdownConfigField
          selection
          data-test="string_mode"
          multiple={false}
          options={[
            {text: 'Plain Text', value: 'plaintext'},
            {text: 'Markdown', value: 'markdown'},
            {text: 'Diff', value: 'diff'},
          ]}
          value={config.mode}
          onChange={(e, {value}) => {
            setMode(value as PanelStringConfigState['mode']);
          }}
        />
      </ConfigPanel.ConfigOption>
      {config.mode === 'diff' && (
        <>
          <ConfigPanel.ConfigOption label="Compare To">
            <S.ConfigExpressionWrap>
              <ConfigPanel.ExpressionConfigField
                expr={props.config?.diffComparand ?? defaultComparand}
                setExpression={setComparand}
              />
            </S.ConfigExpressionWrap>
          </ConfigPanel.ConfigOption>
          <ConfigPanel.ConfigOption label="Diff By">
            <ConfigPanel.ModifiedDropdownConfigField
              selection
              data-test="diff_mode"
              multiple={false}
              options={[
                {text: 'Characters', value: 'chars'},
                {text: 'Words', value: 'words'},
                {text: 'Lines', value: 'lines'},
              ]}
              value={config.diffMode ?? 'chars'}
              onChange={(e, {value}) => {
                setDiffMode(value as PanelStringConfigState['diffMode']);
              }}
            />
          </ConfigPanel.ConfigOption>
        </>
      )}
    </>
  );
};

export const PanelString: React.FC<PanelStringProps> = props => {
  const config = props.config ?? defaultConfig();
  const inputValue = CGReact.useNodeValue(props.input as Node<'string'>);
  const compValue = CGReact.useNodeValue(config.diffComparand ?? props.input);
  const loading = inputValue.loading || compValue.loading;
  const {stringFormat} = useContext(WeaveFormatContext);
  const {spacing} = stringFormat;

  const fullStr = String(inputValue?.result ?? '-');
  const comparandStr = String(compValue?.result ?? ''); // Default comparand is empty string

  const [contentHeight, setContentHeight] = React.useState(0);

  const displayElement = React.useMemo(() => {
    if (config.mode === 'markdown') {
      const contentMarkdown = (
        <Markdown
          condensed={false}
          content={fullStr}
          onContentHeightChange={setContentHeight}
        />
      );
      return (
        <S.StringContainer $spacing={spacing}>
          <S.StringItem $spacing={spacing}>
            <TooltipTrigger
              copyableContent={fullStr}
              content={contentMarkdown}
              triggerContentHeight={contentHeight}>
              {contentMarkdown}
            </TooltipTrigger>
          </S.StringItem>
        </S.StringContainer>
      );
    } else if (config.mode === 'diff') {
      let diff: Diff.Change[] = [];
      switch (config.diffMode) {
        case 'lines':
          diff = Diff.diffLines(fullStr, comparandStr);
          break;
        case 'words':
          diff = Diff.diffWords(fullStr, comparandStr);
          break;
        default:
          diff = Diff.diffChars(fullStr, comparandStr);
      }
      const spans = diff.map((part, index) => {
        const color = part.added
          ? globalStyles.GREEN
          : part.removed
          ? globalStyles.RED
          : 'inherit';
        return (
          <span style={{color}} key={index}>
            {part.value}
          </span>
        );
      });

      const contentDiff = (
        <S.PreformattedMonoString>{spans}</S.PreformattedMonoString>
      );

      return (
        <S.StringContainer $spacing={spacing}>
          <S.StringItem $spacing={spacing}>
            <TooltipTrigger copyableContent={fullStr} content={contentDiff}>
              {contentDiff}
            </TooltipTrigger>
          </S.StringItem>
        </S.StringContainer>
      );
    }

    let parsed: any;
    const trimmedStr = fullStr.trim();
    if (trimmedStr.startsWith('{') && trimmedStr.endsWith('}')) {
      try {
        parsed = JSON.parse(trimmedStr);
      } catch (e) {
        // ignore
        console.error(e);
      }
    }
    // Check if the first 100 characters contain any characters from an RTL script
    // and set the text direction accordingly.
    const textStyle: React.CSSProperties = isRTL(fullStr.slice(0, 100))
      ? {direction: 'rtl', textAlign: 'right'}
      : {};
    let contentPlaintext;
    if (parsed) {
      contentPlaintext = (
        <S.PreformattedJSONString style={textStyle}>
          {JSON.stringify(parsed, null, 2)}
        </S.PreformattedJSONString>
      );
    } else {
      contentPlaintext = (
        <S.PreformattedProportionalString style={textStyle}>
          {fullStr}
        </S.PreformattedProportionalString>
      );
    }

    // plaintext
    return (
      <S.StringContainer data-test-weave-id="string" $spacing={spacing}>
        <S.StringItem $spacing={spacing}>
          <TooltipTrigger copyableContent={fullStr} content={contentPlaintext}>
            {contentPlaintext}
          </TooltipTrigger>
        </S.StringItem>
      </S.StringContainer>
    );
  }, [
    comparandStr,
    config.diffMode,
    config.mode,
    contentHeight,
    fullStr,
    spacing,
  ]);

  const textIsURL = config.mode === 'plaintext' && isURL(fullStr);

  if (loading) {
    return <Panel2Loader />;
  }

  if (textIsURL) {
    const truncateText = fullStr.length > MAX_DISPLAY_LENGTH;
    const displayText =
      '' +
      (truncateText ? fullStr.slice(0, MAX_DISPLAY_LENGTH) + '...' : fullStr);
    return <TargetBlank href={fullStr}>{displayText}</TargetBlank>;
  } else {
    return displayElement;
  }
};

export const Spec: Panel2.PanelSpec = {
  id: 'string',
  icon: 'text-language-alt',
  category: 'Primitive',
  canFullscreen: true,
  Component: PanelString,
  ConfigComponent: PanelStringConfig,
  inputType,
};
