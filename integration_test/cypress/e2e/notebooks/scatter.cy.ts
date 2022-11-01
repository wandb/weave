import {checkWeaveNotebookOutputs} from './notebooks';

describe('scatter notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs('../examples/vis/Scatter.ipynb'));
});
