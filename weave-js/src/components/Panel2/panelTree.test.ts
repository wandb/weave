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

  const getInputNode = (config: ChildPanelFullConfig, path: string[]) => {
    const leaf = PanelTree.getPath(config, path);
    return leaf.input_node;
  };

  const getVarInputNode = (config: ChildPanelFullConfig, path: string[]) => {
    const leaf = getInputNode(config, path);
    if (leaf.nodeType !== 'var') {
      throw new Error('Expected var node for path ' + path.join('.'));
    }
    return leaf;
  };

  const simpleVarOldConfig = PanelTree.makeGroup({
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

  const simpleVarNewConfig = PanelTree.makeGroup({
    sidebar: PanelTree.makeGroup({
      // This is the panel that is renamed
      var1: PanelTree.makePanel(
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

  const nestedVarOldConfig = PanelTree.makeGroup({
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

  const nestedVarNewConfig = PanelTree.makeGroup({
    main: PanelTree.makeGroup({
      // This is the panel that is renamed
      var1: PanelTree.makePanel('a', {
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
        panel0: PanelTree.makePanel(
          'a',
          {
            type: 'const',
            valType: 'string',
            val: 'a',
          },
          {nodeType: 'void', type: 'invalid'}
        ),
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

  describe('updateExpressionVarNamesFromConfig', () => {
    it('updates Panels that refer to a var', () => {
      const newRoot = PanelTree.updateExpressionVarNamesFromConfig(
        simpleVarOldConfig,
        simpleVarNewConfig
      );
      const leaf = getVarInputNode(newRoot, ['main', 'panel0']);
      expect(leaf.varName).toEqual('var1');
    });

    it('does not update nested variables of the same name', () => {
      const newRoot = PanelTree.updateExpressionVarNamesFromConfig(
        nestedVarOldConfig,
        nestedVarNewConfig
      );
      // Checks that the references are what we expect
      const mainPanel1 = getVarInputNode(newRoot, ['main', 'panel1']);
      expect(mainPanel1.varName).toEqual('var1');
      const nestedPanel1 = getVarInputNode(newRoot, [
        'main',
        'panel2',
        'panel1',
      ]);
      expect(nestedPanel1.varName).toEqual('panel0');

      // Checks that the varNames are what we expect
      const nestedPanel0 = getInputNode(newRoot, ['main', 'panel2', 'panel0']);
      expect(nestedPanel0.nodeType).toEqual('void');
      const renamedPanel0 = getInputNode(newRoot, ['main', 'var1']);
      expect(renamedPanel0.nodeType).toEqual('void');
    });
  });

  describe('updateExpressionVarNames', () => {
    it('updates Panels that refer to a var', () => {
      const newRoot = PanelTree.updateExpressionVarNames(
        simpleVarNewConfig,
        [],
        ['sidebar', 'var0'],
        'var0',
        'var1'
      );
      const leaf = getVarInputNode(newRoot, ['main', 'panel0']);
      expect(leaf.varName).toEqual('var1');
    });

    it('does not update nested variables of the same name', () => {
      const newRoot = PanelTree.updateExpressionVarNames(
        nestedVarNewConfig,
        [],
        ['main', 'panel0'],
        'panel0',
        'var1'
      );
      // Checks that the references are what we expect
      const mainPanel1 = getVarInputNode(newRoot, ['main', 'panel1']);
      expect(mainPanel1.varName).toEqual('var1');
      const nestedPanel1 = getVarInputNode(newRoot, [
        'main',
        'panel2',
        'panel1',
      ]);
      expect(nestedPanel1.varName).toEqual('panel0');

      // Checks that the varNames are what we expect
      const nestedPanel0 = getInputNode(newRoot, ['main', 'panel2', 'panel0']);
      expect(nestedPanel0.nodeType).toEqual('void');
      const renamedPanel0 = getInputNode(newRoot, ['main', 'var1']);
      expect(renamedPanel0.nodeType).toEqual('void');
    });
  });
});
