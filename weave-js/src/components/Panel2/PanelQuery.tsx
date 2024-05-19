import {useWeaveContext} from '@wandb/weave/context';
import {
  constNodeUnsafe,
  constString,
  isAssignableTo,
  list,
  listObjectType,
  mapNodes,
  maybe,
  Node,
  NodeOrVoidNode,
  opOr,
  opStringEqual,
  Type,
  varNode,
  voidNode,
  Weave,
} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';
import {Button} from 'semantic-ui-react';

import {TableState} from '../..';
import {
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import {ExpressionView} from './ExpressionView';
import * as Panel from './panel';
import {useUpdateConfig2} from './PanelComp';
import {PanelContextProvider} from './PanelContext';
import {Spec as SelectEditorSpec} from './PanelSelectEditor';
import * as Table from './PanelTable/tableState';
import {updatePreFilter} from './PanelTable/tableState';

interface Condition {
  expression: NodeOrVoidNode;
  editor: ChildPanelFullConfig;
}

const inputType = {type: 'list' as const, objectType: 'any' as const};
interface PanelQueryConfig {
  tableState: Table.TableState;
  pinnedRows: {[groupKey: string]: number[]};
  conditions: Condition[];
  dims: {
    text: TableState.ColumnId;
  };
}
type PanelQueryProps = Panel.PanelProps<typeof inputType, PanelQueryConfig>;

export function defaultPanelQuery(): PanelQueryConfig {
  let tableState = TableState.emptyTable();
  tableState = TableState.appendEmptyColumn(tableState);
  const textColId = tableState.order[tableState.order.length - 1];
  const columnNames = {[textColId]: 'text'};
  tableState = {...tableState, columnNames};

  return {
    tableState,
    pinnedRows: {},
    conditions: [],
    dims: {
      text: textColId,
    },
  };
}

interface ConditionEditorSpec {
  panelId: string;
  initEditor: (expr: NodeOrVoidNode) => ChildPanelFullConfig;
  toFilterClause: (expr: Node, editor: ChildPanelFullConfig) => NodeOrVoidNode;
}

const EDITOR_SPECS: {[key: string]: ConditionEditorSpec} = {
  SelectEditor: {
    panelId: SelectEditorSpec.id,
    initEditor(expr) {
      return {
        vars: {},
        id: SelectEditorSpec.id,
        input_node: constNodeUnsafe({type: 'list', objectType: 'string'}, []),
        config: {
          choices: expr,
        },
      };
    },
    toFilterClause(rowExpr, editor) {
      if (editor.input_node.nodeType !== 'const') {
        throw new Error('SelectEditor requires const input');
      }
      const selected = editor.input_node.val;
      if (selected.length === 0) {
        return voidNode();
      }
      let clause = opStringEqual({lhs: rowExpr, rhs: constString(selected[0])});
      for (let i = 1; i < selected.length; i++) {
        clause = opOr({
          lhs: clause,
          rhs: opStringEqual({lhs: rowExpr, rhs: constString(selected[i])}),
        });
      }
      return clause;
    },
  },
};

const conditionEditorsForType = (type: Type): ConditionEditorSpec[] => {
  if (isAssignableTo(type, list(maybe('string')))) {
    return [EDITOR_SPECS.SelectEditor];
  }
  return [];
};

const toFilterExpression = (
  weave: Weave,
  input: Node,
  config: PanelQueryConfig
): NodeOrVoidNode => {
  const clauses = config.conditions.map(condition => {
    const withRow = mapNodes(condition.expression, (checkNode: any) => {
      if (checkNode.nodeType === 'var' && checkNode.varName === 'queryInput') {
        return varNode(listObjectType(input.type), 'row');
      }
      // TODO: This type remapping is no good
      if (checkNode.nodeType === 'output') {
        const opDef = weave.client.opStore.getOpDef(checkNode.fromOp.name);
        const newOutputType =
          typeof opDef.outputType === 'function'
            ? opDef.outputType(checkNode.fromOp.inputs as any)
            : opDef.outputType;
        return {
          ...checkNode,
          type: newOutputType,
        };
      }
      return checkNode;
    }) as Node;
    const editorSpec = EDITOR_SPECS[condition.editor.id];
    if (editorSpec == null) {
      return voidNode();
    }
    return editorSpec.toFilterClause(withRow, condition.editor);
  });
  console.log('CLAUSES', clauses);
  return clauses[0] ?? voidNode();
};

type PanelQueryConditionProps = PanelQueryProps & {
  condition: Condition;
  index: number;
};

const usePanelQueryConditionCommon = (props: PanelQueryConditionProps) => {
  const {condition, input} = props;
  const weave = useWeaveContext();

  const updateConfig2 = useUpdateConfig2(props);

  const newVars = useMemo(() => {
    return {
      queryInput: varNode(props.input.type, 'input'),
    };
  }, [props.input.type]);
  const updateCondition = useCallback(
    (newCondition: Partial<Condition>) => {
      updateConfig2(oldConfig => {
        const newConditions = [...oldConfig.conditions];
        newConditions[props.index] = {
          ...oldConfig.conditions[props.index],
          ...newCondition,
        };
        const newConfig = {
          ...oldConfig,
          conditions: newConditions,
        };
        const newFilterExpr = toFilterExpression(weave, input, newConfig);
        const newTableState = updatePreFilter(
          newConfig.tableState,
          newFilterExpr
        );
        return {
          ...newConfig,
          tableState: newTableState,
        };
      });
    },
    [input, props.index, updateConfig2, weave]
  );
  const updateConditionExpr = useCallback(
    async (newExpr: NodeOrVoidNode) => {
      updateCondition({expression: newExpr});
      const allowedEditorsSpecs = conditionEditorsForType(newExpr.type);
      console.log('UPDATE COND', newExpr, allowedEditorsSpecs);
      const currentEditorValid = allowedEditorsSpecs.find(
        editor => editor.panelId === condition.editor.id
      );
      if (currentEditorValid == null) {
        if (allowedEditorsSpecs.length > 0) {
          const newEditorSpec = allowedEditorsSpecs[0];
          const newEditor = newEditorSpec.initEditor(newExpr);
          updateCondition({editor: newEditor});
        } else {
          updateCondition({
            editor: {
              vars: {},
              input_node: voidNode(),
              id: 'Expression',
              config: undefined,
            },
          });
        }
      }
    },
    [condition.editor.id, updateCondition]
  );

  const updateEditorConfig = useCallback(
    (newConfig: ChildPanelFullConfig) => {
      updateCondition({editor: newConfig});
    },
    [updateCondition]
  );

  return useMemo(
    () => ({
      newVars,
      condition,
      updateConditionExpr,
      updateEditorConfig,
    }),
    [condition, newVars, updateConditionExpr, updateEditorConfig]
  );
};

export const PanelQueryConditionConfigComponent: React.FC<
  PanelQueryConditionProps
> = props => {
  const {newVars, condition, updateConditionExpr, updateEditorConfig} =
    usePanelQueryConditionCommon(props);
  return (
    <>
      <PanelContextProvider newVars={newVars}>
        <ConfigPanel.ConfigOption label={`expr`}>
          <ConfigPanel.ExpressionConfigField
            expr={condition.expression}
            setExpression={updateConditionExpr}
          />
        </ConfigPanel.ConfigOption>
        <ConfigPanel.ChildConfigContainer>
          <ChildPanelConfigComp
            config={condition.editor}
            updateConfig={updateEditorConfig}
          />
        </ConfigPanel.ChildConfigContainer>
      </PanelContextProvider>
    </>
  );
};

export const PanelQueryConditionComponent: React.FC<
  PanelQueryConditionProps
> = props => {
  const {newVars, condition, updateEditorConfig} =
    usePanelQueryConditionCommon(props);

  console.log('CONDITION EDITOR', condition.editor);

  return (
    <div style={{height: '100%'}}>
      <ExpressionView node={condition.expression as any} />
      <div style={{maxHeight: 300, overflow: 'auto'}}>
        <PanelContextProvider newVars={newVars}>
          <ChildPanel
            config={condition.editor}
            updateConfig={updateEditorConfig}
          />
        </PanelContextProvider>
      </div>
    </div>
  );
};

export const PanelQueryConfigComponent: React.FC<PanelQueryProps> = props => {
  const updateConfig2 = useUpdateConfig2(props);
  const config = props.config!;

  const addCondition = useCallback(() => {
    updateConfig2(oldConfig => {
      return {
        ...oldConfig,
        conditions: [
          ...oldConfig.conditions,
          {
            expression: voidNode(),
            editor: {
              vars: {},
              input_node: voidNode(),
              id: 'Expression',
              config: undefined,
            },
          },
        ],
      };
    });
  }, [updateConfig2]);

  return (
    <ConfigPanel.ConfigSection label={`Conditions`}>
      {config.conditions.map((condition, i) => (
        <PanelQueryConditionConfigComponent
          key={i}
          {...props}
          condition={condition}
          index={i}
        />
      ))}
      <Button size="mini" onClick={addCondition}>
        Add Condition
      </Button>
    </ConfigPanel.ConfigSection>
  );
};

export const PanelQuery: React.FC<PanelQueryProps> = props => {
  const config = props.config!;

  return (
    <div
      style={{
        height: '100%',
        paddingLeft: 16,
        display: 'flex',
        flexDirection: 'column',
      }}>
      {config.conditions.map((condition, i) => (
        <PanelQueryConditionComponent
          key={i}
          {...props}
          condition={condition}
          index={i}
        />
      ))}
    </div>
  );
};

export const Spec: Panel.PanelSpec = {
  hidden: true,
  id: 'Query',
  initialize: defaultPanelQuery,
  ConfigComponent: PanelQueryConfigComponent,
  Component: PanelQuery,
  inputType,
};
