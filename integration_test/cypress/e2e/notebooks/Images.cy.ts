import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/images.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/images.ipynb')
    );
});