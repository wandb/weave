import {checkWeaveNotebookOutputs} from './notebooks';

describe.skip('confusion notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs('../examples/vis/Confusion.ipynb'));
});
