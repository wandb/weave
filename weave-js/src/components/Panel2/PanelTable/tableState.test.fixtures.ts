import {
  constString,
  createLocalClient,
  dereferenceAllVars,
  emptyStack,
  Frame,
  Node,
  opArtifactVersionFile,
  opFileTable,
  opRootArtifactVersion,
  opTableRows,
  pushFrame,
  WeaveInterface,
} from '@wandb/weave/core';

import {WeaveApp} from '../../..';
import * as ServerApiTest from '../../../core/_external/backendProviders/serverApiTest2';
import * as Table from './tableState';

export function testClient() {
  return createLocalClient(new ServerApiTest.Client());
}

export function testWeave() {
  return new WeaveApp(testClient());
}

export async function getTableRowsNode(
  fileName = 'train_iou_score_table.table.json'
) {
  const weave = testWeave();
  const artifactVersion = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('dsviz_demo'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('train_results:v2'),
  });
  const artifactFile = opArtifactVersionFile({
    artifactVersion,
    path: constString(fileName),
  });
  const artifactTable = opFileTable({
    file: artifactFile as any,
  });
  const tableRows = opTableRows({
    table: artifactTable as any,
  });
  return await weave.refineNode(tableRows, []);
}

export async function initTable(
  weave: WeaveInterface,
  inputArrayNode: Node,
  pickCols?: string[]
) {
  return Table.initTableWithPickColumns(inputArrayNode, weave, pickCols);
}

// This matches what PanelTable2 does
export async function getTableCellValues(
  ts: Table.TableState,
  node: Node,
  frame?: Frame
) {
  const weave = testWeave();
  const resultTableNode = Table.tableGetResultTableArrayRowsNode(
    ts,
    node,
    weave
  );
  const dereffed = dereferenceAllVars(
    resultTableNode,
    pushFrame(emptyStack(), frame ?? {})
  ).node;
  return await weave.client.query(dereffed as Node);
}

export function getTableCellTypes(ts: Table.TableState) {
  return ts.groupBy
    .concat(Table.getColumnRenderOrder(ts))
    .map(colId => ts.columnSelectFunctions[colId].type);
}
