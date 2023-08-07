import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/reference/simple_api_test.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/simple_api_test.ipynb')
    );
});