import {checkWeaveNotebookOutputs} from './notebooks';

describe('distribution notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs('../examples/vis/Distribution.ipynb'));
});
