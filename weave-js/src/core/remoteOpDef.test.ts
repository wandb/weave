import {defaultLanguageBinding} from './language';
import {OutputNode} from './model';
import {Type} from './model/types';
import * as Op from './ops';
import {buildOpStoreFromOpList, ServerOpDef} from './opStore/remoteOpStore';
import {determineOutputType} from './opStore/static';
import * as testData from './test_op_def_data.copy.json';

// TODO: Validate execution in the future (requires a server) - currently just tests types
describe('loading remote op store defs', () => {
  // This just just a way to force the ops to be loaded
  console.log(Op.opObjGetAttr);
  const opNames = Object.keys(testData.op_defs);
  const ops: ServerOpDef[] = Object.values(testData.op_defs).map(
    v => v.def as ServerOpDef
  );

  const {remoteOpStore} = buildOpStoreFromOpList({data: ops});

  opNames.forEach(name => {
    describe(`${name}`, () => {
      const op = remoteOpStore.getOpDef(name);

      it('should load', () => {
        expect(op).toBeDefined();
      });
      const subtests: Array<{
        inputs: {[key: string]: OutputNode};
        output: {type: Type; val: any};
      }> = (testData.op_defs as any)[name].example_io ?? [];
      subtests.forEach((subtest, ndx) => {
        const inputTypes = Object.entries(subtest.inputs)
          .map(e => {
            return `${e[0]}: ${defaultLanguageBinding.printType(e[1].type)}`;
          })
          .join(', ');
        it(`should correctly handle io ${inputTypes}`, () => {
          expect(determineOutputType(op, subtest.inputs)).toEqual(
            subtest.output.type
          );
        });
      });
    });
  });
});
