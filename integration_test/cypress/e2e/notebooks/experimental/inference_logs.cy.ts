import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/inference_logs.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/inference_logs.ipynb')
    );
});