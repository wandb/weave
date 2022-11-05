import {checkWeaveNotebookOutputs} from './notebooks';

describe.only('../examples/Bertviz.ipynb notebook test', () => {
  it('passes', () => checkWeaveNotebookOutputs('../examples/Bertviz.ipynb'));
});
