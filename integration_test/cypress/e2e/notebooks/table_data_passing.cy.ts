import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/table_data_passing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/table_data_passing.ipynb')
    );
});