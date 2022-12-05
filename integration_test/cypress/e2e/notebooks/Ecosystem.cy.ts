import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/Ecosystem.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/Ecosystem.ipynb')
    );
});