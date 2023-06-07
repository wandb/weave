import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Monitor3.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Monitor3.ipynb')
    );
});