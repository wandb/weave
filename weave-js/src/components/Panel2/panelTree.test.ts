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
});