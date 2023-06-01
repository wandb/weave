import * as _ from 'lodash';

import type {Client} from '../../client';
import {EngineClient} from '../../client';
import * as HL from '../../hl';
import type {ImageType, Node, Type} from '../../model';
import {
  concreteWithNamedTag,
  constNumber,
  constString,
  detectColumnTypes,
  getValueFromTaggedValue,
  isAssignableTo,
  isForeignIndexWBType,
  isForeignKeyWBType,
  isList,
  isTable,
  list,
  mappableNullableSkipTaggable,
  mappableNullableSkipTaggableValAsync,
  maybe,
  nullableOneOrMany,
  nullableTaggableAsync,
  nullableTaggableValue,
  tableNeedsFloatColumnConversion,
  typedDict,
  union,
  withTableRowTag,
} from '../../model';
import {makeOp} from '../../opStore';
import {docType} from '../../util/docs';
import {makeTagGetterOp} from '../opKinds';
import {opIndex} from '../primitives/list';
import {opArtifactVersionFile} from './artifactVersion';
import {opAssetArtifactVersion} from './asset';
import {opFileContents, opFileTable} from './file';
import {makeResolveOutputTypeFromOp} from './refineOp';

// This method makes up for a mistake in the python weave type system.
// The Python `image-file` does not contain the key `box`, `mask`, `box_score`,
// and `class` data required to properly produce configs without inspecting the data.
// As a result. the PanelImage (and it's config) are unnecessarily complex and slow.
// Moreover, when viewing a PanelImage, it actually update's its own config with the
// mask/box data based on the actual data payload. This can cause React to continuously
// update in certain edge cases. Therefore, the fix is to 1) update the python client
// to properly report the associated image type information; and 2) make a backwards compatible
// patch like the following to at least infer the types in cases where they are not available.
// This pattern of needing to inspect the data to determine types is not ideal, but
// must be done in some cases (for example in linked tables).
// TODO: extend to work with lists
const patchImageFileTypes = async (
  client: Client,
  table: any,
  tableNode: Node,
  inColType: Type,
  colNdx: number
) => {
  if (isAssignableTo(inColType, maybe({type: 'image-file'}))) {
    inColType = await nullableTaggableAsync(inColType, async colType => {
      const imgColType = colType as ImageType;
      const hasClassInfo = imgColType.classMap != null;
      if (hasClassInfo) {
        return imgColType;
      }
      // If the type does not come pre-loaded, we need to inspect the data to determine the type.
      // We will look at the first 10 rows of the table to determine the type.
      let nonNullRowsEvaluated = 0;
      let maskKeys: string[] = [];
      let boxKeys: string[] = [];
      imgColType.boxScoreKeys = [];
      imgColType.classMap = {};
      for (const row of table.data) {
        const imageExample = row[colNdx];
        if (imageExample != null) {
          if (imageExample.masks != null) {
            maskKeys = _.union(maskKeys, Object.keys(imageExample.masks));
          }
          if (imageExample.boxes != null) {
            boxKeys = _.union(boxKeys, Object.keys(imageExample.boxes));
            for (const boxItem of Object.values(imageExample.boxes)) {
              if ((boxItem as any).scores != null) {
                imgColType.boxScoreKeys = _.union(
                  imgColType.boxScoreKeys,
                  Object.keys((boxItem as any).scores)
                );
              }
            }
          }
          if (imageExample.classes?.path != null) {
            const contentsNode = opFileContents({
              file: opArtifactVersionFile({
                artifactVersion: opAssetArtifactVersion({
                  asset: tableNode,
                }) as any,
                path: constString(imageExample.classes?.path),
              }) as any,
            });
            const contentRaw = await client.query(contentsNode);
            const classContent = JSON.parse(contentRaw);
            if (classContent.class_set != null) {
              for (const classItem of classContent.class_set) {
                if (
                  classItem.id != null &&
                  classItem.name != null &&
                  imgColType.classMap[String(classItem.id)] == null
                ) {
                  imgColType.classMap[String(classItem.id)] = String(
                    classItem.name
                  );
                }
              }
            }
          }
          nonNullRowsEvaluated += 1;
          if (nonNullRowsEvaluated >= 10) {
            break;
          }
        }
      }
      const classKeys = Object.keys(imgColType.classMap);
      imgColType.maskLayers = _.fromPairs(
        _.map(maskKeys, key => {
          return [key, classKeys];
        })
      );
      imgColType.boxLayers = _.fromPairs(
        _.map(boxKeys, key => {
          return [key, classKeys];
        })
      );
      return imgColType;
    });
  }
  return inColType;
};

const tableRowTypeFromTableData = async (
  client: Client,
  tableResult: any,
  tableNode: Node
) => {
  const table = tableResult;
  if (table == null) {
    return 'none';
  }

  const colTypes = detectColumnTypes(table);
  const useFloatConversion = tableNeedsFloatColumnConversion(table);
  const propertyTypes: {[key: string]: Type} = {};
  for (let i = 0; i < table.columns.length; i++) {
    propertyTypes[table.columns[i]] = await patchImageFileTypes(
      client,
      table,
      tableNode,
      colTypes[i],
      i
    );
  }

  if (table.column_types) {
    const tableArtifactNode = opAssetArtifactVersion({
      asset: tableNode,
    });
    const types = table.column_types.params.type_map;
    for (const colName of table.columns) {
      const colType = types[useFloatConversion ? `${colName}.0` : colName];
      if (
        colType != null &&
        (isForeignIndexWBType(colType) || isForeignKeyWBType(colType))
      ) {
        const peerTableRowsNode = opTableRows({
          table: opFileTable({
            file: opArtifactVersionFile({
              artifactVersion: tableArtifactNode as any,
              path: constString(colType.params.table),
            }) as any,
          }) as any,
        });
        const peerTableRowsNodeRefined = await HL.refineNode(
          client,
          peerTableRowsNode,
          []
        );
        if (
          peerTableRowsNodeRefined &&
          peerTableRowsNodeRefined.type &&
          isList(peerTableRowsNodeRefined.type)
        ) {
          propertyTypes[colName] = peerTableRowsNodeRefined.type.objectType;
        }
      }
    }
  }
  return list(withTableRowTag(typedDict(propertyTypes), tableNode.type));
};

export const opTableRowsType = makeOp({
  hidden: true,
  name: 'table-rowsType',
  argTypes: {
    table: nullableOneOrMany({type: 'table', columnTypes: {}}),
  },
  description: `Returns the type of rows of a ${docType('table')}`,
  argDescriptions: {
    table: `A ${docType('table')}`,
  },
  returnValueDescription: `The type of rows of the ${docType('table')}`,
  returnType: 'type',
  resolver: async ({table}, forwardGraph, forwardOp, context, engine) => {
    if (table == null) {
      return 'none';
    }

    const client = new EngineClient(engine());
    const tableInput = forwardOp.op.inputs.table;

    const unwrappedTable: any[] = getValueFromTaggedValue(table);

    if (isList(nullableTaggableValue(tableInput.type))) {
      const allTypes = await Promise.all(
        unwrappedTable.map((tr, i) =>
          tableRowTypeFromTableData(
            client,
            getValueFromTaggedValue(tr),
            opIndex({arr: tableInput, index: constNumber(i)})
          )
        )
      );
      const innerType = allTypes.length === 0 ? 'none' : union(allTypes);
      return list(innerType, allTypes.length, allTypes.length);
    }

    return tableRowTypeFromTableData(
      client,
      unwrappedTable,
      forwardOp.op.inputs.table
    );
  },
});

// TODO: This should really use opKinds StandardOp. It currently sticks
// outer table tags onto the rows immediately. With StandardOp it wouldn't.
// We'd need to fix opConcat and maybe opJoin to handle tags around each
// array.
// TODO: mapped linked table behavior does not have a unit test! We really
// need add one as this is one of the most complex uses of the op system.
export const opTableRows = makeOp({
  name: 'table-rows',
  argTypes: {
    table: nullableOneOrMany({type: 'table', columnTypes: {}}),
  },
  description: `Returns the rows of a ${docType('table')}`,
  argDescriptions: {
    table: `A ${docType('table')}`,
  },
  returnValueDescription: `The rows of the ${docType('table')}`,
  returnType: inputs => {
    return mappableNullableSkipTaggable(inputs.table.type, t => {
      if (!isTable(t)) {
        throw new Error('opTableRows: expected table');
      }
      return list(withTableRowTag(typedDict(t.columnTypes), inputs.table.type));
    });
  },
  resolver: async (inputs, forwardGraph, forwardOp, context, engine) => {
    return mappableNullableSkipTaggableValAsync(
      inputs.table,
      async (table, tableWithTags, mapIndex) => {
        const peerIndexTables: {[column: string]: any[]} = {};
        const peerLookupTables: {[column: string]: {[key: string]: any}} = {};
        if (table.column_types) {
          let tableNode = forwardOp.op.inputs.table;
          if (mapIndex != null) {
            tableNode = opIndex({arr: tableNode, index: constNumber(mapIndex)});
          }
          const tableArtifactNode = opAssetArtifactVersion({
            asset: tableNode,
          });
          const types = table.column_types.params.type_map;
          const useFloatConversion = tableNeedsFloatColumnConversion(table);
          for (const colName of table.columns) {
            const colType =
              types[useFloatConversion ? `${colName}.0` : colName];
            let peerTable: any = null;
            if (
              colType != null &&
              (isForeignIndexWBType(colType) || isForeignKeyWBType(colType))
            ) {
              const peerTableRowsNode = opTableRows({
                table: opFileTable({
                  file: opArtifactVersionFile({
                    artifactVersion: tableArtifactNode as any,
                    path: constString(colType.params.table),
                  }) as any,
                }) as any,
              });
              peerTable = (
                await engine().executeNodes([peerTableRowsNode], false)
              )[0];
              if (isForeignIndexWBType(colType)) {
                peerIndexTables[colName] = peerTable;
              } else {
                peerLookupTables[colName] = {};
                // Note: this only links to the last value in the array (assumed unique link)
                peerTable.forEach((row: any) => {
                  const val = row._value ? row._value : row;
                  if (val[colType.params.col_name]) {
                    peerLookupTables[colName][val[colType.params.col_name]] =
                      row;
                  }
                });
              }
            }
          }
        }
        return table.data.map((row: any, ndx: number) => {
          const rowResult: {[key: string]: any} = {};
          for (let i = 0; i < table.columns.length; i++) {
            if (table.columns[i] in peerIndexTables) {
              rowResult[table.columns[i]] =
                peerIndexTables[table.columns[i]][row[i]];
            } else if (table.columns[i] in peerLookupTables) {
              rowResult[table.columns[i]] =
                peerLookupTables[table.columns[i]][row[i]];
            } else {
              rowResult[table.columns[i]] = row[i];
            }
          }
          return concreteWithNamedTag('table', tableWithTags, rowResult);
        });
      }
    );
  },
  resolveOutputType: makeResolveOutputTypeFromOp(opTableRowsType, ['table']),
});

// Hide for now, its showing up at the top of suggestions
export const opTableRowTable = makeTagGetterOp({
  hidden: true,
  name: 'tablerow-table',
  tagName: 'table',
  tagType: {type: 'table', columnTypes: {}},
});

// export const opTableRowIndex = Graph.makeOp({
//   hidden: true,
//   name: 'tablerow-index',
//   argTypes: {
//     obj: TypeHelpers.maybe(Types.oneOrMany(TypeHelpers.withTableRowMixin('any', 'any'))),
//   },
//   returnType: inputs => {
//     const {obj} = inputs;
//     const objType = obj.type;
//     return OpDefHelpers.nullable(objType, t =>
//       OpTypes.mappable(t, v => {
//         if (!TypeHelpers.isTaggedValue(v)) {
//           throw new Error('invalid');
//         }
//         return 'number';
//       })
//     );
//   },
//   resolver: inputs => {
//     const {obj} = inputs;
//     return OpDefHelpers.nullableVal(obj, t =>
//       OpTypes.mappableVal(t, (v: any) => v.t.tableRow.index)
//     );
//   },
// });
