import {checkWeaveNotebookOutputs} from './notebooks';

describe('confusion notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs('../examples/vis/Confusion.ipynb'));
});
