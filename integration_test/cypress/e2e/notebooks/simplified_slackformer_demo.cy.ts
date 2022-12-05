import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/simplified_slackformer_demo.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/simplified_slackformer_demo.ipynb')
    );
});