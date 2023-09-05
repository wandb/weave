import {ChildPanelFullConfig} from './ChildPanel';
import * as PanelTree from './panelTree';

describe('PanelTree', () => {
  it('non-group path', async () => {
    const root = PanelTree.makeGroup({
      main: PanelTree.makePanel('EachColumn', {
        render: PanelTree.makePanel('a', {}),
      }),
    });
    const leaf = PanelTree.getPath(root, ['main', 'render']);
    expect(leaf.id).toEqual('a');
    const newRoot = PanelTree.setPath(
      root,
      ['main', 'render'],
      PanelTree.makePanel('b', {})
    );
    const newLeaf = PanelTree.getPath(newRoot, ['main', 'render']);
    expect(newLeaf.id).toEqual('b');
  });

  describe('updateExpressionVarNames', () => {
    const getVarInputNode = (config: ChildPanelFullConfig, path: string[]) => {
      const leaf = PanelTree.getPath(config, path);
      if (leaf.input_node.nodeType !== 'var') {
        fail("input_node wasn't a var");
      }
      return leaf.input_node;
    };

    it('updates Panels that refer to a var', () => {
      const root = PanelTree.makeGroup({
        sidebar: PanelTree.makeGroup({
          var0: PanelTree.makePanel(
            'a',
            {},
            {
              nodeType: 'const',
              type: 'string',
              val: 'a',
            }
          ),
        }),
        main: PanelTree.makeGroup({
          panel0: PanelTree.makePanel(
            'a',
            {},
            {
              nodeType: 'var',
              type: {type: 'const', valType: 'string', val: 'a'},
              varName: 'var0',
            }
          ),
        }),
      });

      const newRoot = PanelTree.updateExpressionVarNames(
        root,
        [],
        ['sidebar', 'var0'],
        'var0',
        'var1'
      );

      const leaf = getVarInputNode(newRoot, ['main', 'panel0']);
      expect(leaf.varName).toEqual('var1');
    });

    const commonRoot = PanelTree.makeGroup({
      main: PanelTree.makeGroup({
        panel0: PanelTree.makePanel('a', {
          type: 'const',
          valType: 'string',
          val: 'a',
        }),
        panel1: PanelTree.makePanel(
          'a',
          {},
          {
            nodeType: 'var',
            type: {type: 'const', valType: 'string', val: 'a'},
            varName: 'panel0',
          }
        ),
        panel2: PanelTree.makeGroup({
          panel0: PanelTree.makePanel('a', {
            type: 'const',
            valType: 'string',
            val: 'a',
          }),
          panel1: PanelTree.makePanel(
            'a',
            {},
            {
              nodeType: 'var',
              type: {type: 'const', valType: 'string', val: 'a'},
              varName: 'panel0',
            }
          ),
        }),
      }),
    });

    it('does not update nested variables of the same name', () => {
      const newRoot = PanelTree.updateExpressionVarNames(
        commonRoot,
        [],
        ['main', 'panel0'],
        'panel0',
        'var1'
      );
      const leaf = getVarInputNode(newRoot, ['main', 'panel1']);
      const leaf2 = getVarInputNode(newRoot, ['main', 'panel2', 'panel0']);
      const leaf3 = getVarInputNode(newRoot, ['main', 'panel2', 'panel1']);
      expect(leaf.varName).toEqual('var1');
      expect(leaf2).toBeDefined();
      expect(leaf3.varName).toEqual('panel0');
    });

    it('does not update higher level variables of the same name', () => {
      const newRoot = PanelTree.updateExpressionVarNames(
        commonRoot,
        [],
        ['main', 'panel2', 'panel0'],
        'panel0',
        'var1'
      );

      const leaf = getVarInputNode(newRoot, ['main', 'panel1']);
      const leaf2 = getVarInputNode(newRoot, ['main', 'panel0']);
      const leaf3 = getVarInputNode(newRoot, ['main', 'panel2', 'panel1']);
      expect(leaf.varName).toEqual('panel0');
      expect(leaf2).toBeDefined();
      expect(leaf3.varName).toEqual('var1');
    });
  });
});
