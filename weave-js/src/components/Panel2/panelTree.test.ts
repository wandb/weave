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

  describe('updateVarNames', () => {
    it ('updateVarNames', () => {
      const root = PanelTree.makeGroup({
        sidebar: PanelTree.makeGroup({
          var0: PanelTree.makePanel('a', {}, {
            nodeType: "const",
            type: "string",
            val: "a"}),
        }),
        main: PanelTree.makeGroup({
          panel0: PanelTree.makePanel('a', {}, {
            nodeType: "var",
            type: {type: 'const', valType: 'string', val: 'a'},
            varName: "var0"
          }),
        }),
      });

      const newRoot = PanelTree.updateExpressionVarNames(root, [], ['sidebar', 'var0'], 'var0', 'var1');

      const leaf = PanelTree.getPath(newRoot, ['main', 'panel0']);
      expect(leaf.input_node.varName).toEqual('var1');
    });

  });
});
