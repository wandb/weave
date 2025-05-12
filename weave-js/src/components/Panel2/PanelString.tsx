import 'react-json-view-lite/dist/index.css';

import Markdown from '@wandb/weave/common/components/Markdown';
import * as globalStyles from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {
  constString,
  maybe,
  Node,
  NodeOrVoidNode,
  opGetRunTag,
  opIsNone,
  opPick,
  opRunId,
  varNode,
  weaveIf,
} from '@wandb/weave/core';
import * as Diff from 'diff';
import React, {useContext} from 'react';
import {allExpanded, defaultStyles, JsonView} from 'react-json-view-lite';

import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import * as ConfigPanel from './ConfigPanel';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {usePanelContext} from './PanelContext';
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

type JsonExpandLevel = number | 'all';

interface PanelStringConfigState {
  mode: 'plaintext' | 'markdown' | 'diff';

  // Plaintext only:
  // Whether to render escaped whitespace characters
  renderWhitespace?: boolean;
  // nesting level (undefined defaults to 1)
  jsonExpandLevel?: JsonExpandLevel;

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
    renderWhitespace: false,
    jsonExpandLevel: 1,
  };
};

const defaultComparand = constString('');

export const PanelStringConfig: React.FC<PanelStringProps> = props => {
  const config = props.config ?? defaultConfig();
  const updateConfig = props.updateConfig;

  const weave = useWeaveContext();
  // Cast the input to any type first before using it
  const inputNode = props.input as Node;
  const inputValue = CGReact.useNodeValue(inputNode);

  // Check if the input string is JSON
  const isJsonString = React.useMemo(() => {
    if (inputValue.loading || !inputValue.result) {
      return false;
    }

    const trimmedStr = String(inputValue.result).trim();
    if (trimmedStr.startsWith('{') && trimmedStr.endsWith('}')) {
      try {
        JSON.parse(trimmedStr);
        return true;
      } catch (e) {
        return false;
      }
    }
    return false;
  }, [inputValue]);

  const setMode = React.useCallback(
    (mode: PanelStringConfigState['mode']) => {
      updateConfig({...config, mode});
    },
    [config, updateConfig]
  );
  const setRenderWhitespace = React.useCallback(
    (renderWhitespace: boolean) => {
      updateConfig({...config, renderWhitespace});
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
  const setJsonExpandLevel = React.useCallback(
    (jsonExpandLevel: JsonExpandLevel) => {
      updateConfig({...config, jsonExpandLevel});
    },
    [config, updateConfig]
  );

  // Generate the options for JSON expand levels
  const expandLevelOptions = React.useMemo(() => {
    return [
      {text: 'None (0)', value: 0},
      {text: 'Level 1', value: 1},
      {text: 'Level 2', value: 2},
      {text: 'Level 3', value: 3},
      {text: 'Level 4', value: 4},
      {text: 'Level 5', value: 5},
      {text: 'Expand All', value: 'all'},
    ];
  }, []);

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
      {config.mode === 'plaintext' && (
        <ConfigPanel.ConfigOption label="Render Whitespace">
          <ConfigPanel.ModifiedDropdownConfigField
            selection
            data-test="render-whitespace"
            multiple={false}
            options={[
              {text: 'False', value: false},
              {text: 'True', value: true},
            ]}
            value={config.renderWhitespace ?? false}
            onChange={(e, {value}) => {
              setRenderWhitespace(value as boolean);
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
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
      {config.mode === 'plaintext' && isJsonString && (
        <ConfigPanel.ConfigOption label="JSON Expand Level">
          <ConfigPanel.ModifiedDropdownConfigField
            selection
            data-test="json_expand_level"
            multiple={false}
            options={expandLevelOptions}
            value={config.jsonExpandLevel ?? 1}
            onChange={(e, {value}) => {
              setJsonExpandLevel(value as JsonExpandLevel);
            }}
          />
        </ConfigPanel.ConfigOption>
      )}
    </>
  );
};

/**
 * Converts string representations of whitespace characters to actual whitespace characters.
 * For example: '\\n' becomes an actual newline, '\\t' becomes an actual tab.
 */
const convertWhitespaceChars = (str: string): string => {
  return str.replace(/\\[nrt]/g, match => {
    switch (match) {
      case '\\n':
        return '\n';
      case '\\r':
        return '\r';
      case '\\t':
        return '\t';
      default:
        return match;
    }
  });
};

export const PanelString: React.FC<PanelStringProps> = props => {
  const config = props.config ?? defaultConfig();
  const {frame} = usePanelContext();
  let inputNode = props.input as Node<'string'>;
  if (
    props.input.nodeType === 'output' &&
    props.input.fromOp.name === 'run-name' &&
    frame.customRunNames != null
  ) {
    const customRunNameNode = opPick({
      obj: varNode(frame.customRunNames.type, 'customRunNames'),
      key: opRunId({run: opGetRunTag({obj: props.input})}),
    }) as Node<'string'>;

    inputNode = weaveIf(
      opIsNone({
        val: customRunNameNode,
      }),
      props.input,
      customRunNameNode
    ) as Node<'string'>;
  }
  const inputValue = CGReact.useNodeValue(inputNode);
  const compValue = CGReact.useNodeValue(config.diffComparand ?? props.input);
  const loading = inputValue.loading || compValue.loading;
  const {stringFormat} = useContext(WeaveFormatContext);
  const {spacing} = stringFormat;

  const fullStr = String(inputValue?.result ?? '-');
  const comparandStr = String(compValue?.result ?? ''); // Default comparand is empty string

  const [contentHeight, setContentHeight] = React.useState(0);

  const displayElement = React.useMemo(() => {
    const getJsonExpandMode = () => {
      const level = config.jsonExpandLevel ?? 1;

      if (level === 'all') {
        return allExpanded; // Use the built-in allExpanded function
      }

      if (level <= 0) {
        return () => false; // Don't expand anything
      }

      return (nodeLevel: number) => nodeLevel < level;
    };
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
        <JsonView
          data={parsed}
          style={{
            ...defaultStyles,
            ...textStyle,
            container: 'background: white;',
          }}
          shouldExpandNode={getJsonExpandMode()}
        />
      );
    } else {
      // Handle plaintext with renderWhitespace option
      if (config.renderWhitespace && !parsed) {
        contentPlaintext = (
          <S.PreformattedMonoString
            style={{...textStyle, whiteSpace: 'pre-wrap'}}>
            {convertWhitespaceChars(fullStr)}
          </S.PreformattedMonoString>
        );
      } else {
        contentPlaintext = (
          <S.PreformattedProportionalString style={textStyle}>
            {fullStr}
          </S.PreformattedProportionalString>
        );
      }
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
    config.renderWhitespace,
    contentHeight,
    fullStr,
    spacing,
    config.jsonExpandLevel,
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
