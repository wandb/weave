import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Weave engine tracing.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Weave engine tracing.ipynb')
    );
});