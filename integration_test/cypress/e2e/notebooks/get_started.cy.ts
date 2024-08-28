import { checkWeaveNotebookOutputs } from './notebooks';

describe('../weave/legacy/examples/get_started.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../weave/legacy/examples/get_started.ipynb')
    );
});
