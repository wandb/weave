import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/craiyon.ipynb')
    );
});