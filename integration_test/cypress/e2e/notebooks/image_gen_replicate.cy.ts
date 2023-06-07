import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/image_gen_replicate.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/image_gen_replicate.ipynb')
    );
});