import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Images.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Images.ipynb')
    );
});