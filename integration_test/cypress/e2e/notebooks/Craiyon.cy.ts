import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Craiyon.ipynb')
    );
});