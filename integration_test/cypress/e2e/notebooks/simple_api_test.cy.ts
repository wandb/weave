import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/simple_api_test.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/simple_api_test.ipynb')
    );
});