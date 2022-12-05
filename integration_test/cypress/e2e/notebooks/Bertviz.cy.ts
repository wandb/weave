import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Bertviz.ipynb notebook test', () => {
  it('passes', () => checkWeaveNotebookOutputs('../examples/Bertviz.ipynb'));
});
