import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/table_data_passing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/table_data_passing.ipynb')
    );
});