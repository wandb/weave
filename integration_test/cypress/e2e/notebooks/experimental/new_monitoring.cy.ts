import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/new_monitoring.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs('../examples/experimental/new_monitoring.ipynb'));
});
