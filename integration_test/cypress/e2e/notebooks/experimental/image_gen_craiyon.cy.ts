import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/experimental/image_gen_craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/experimental/image_gen_craiyon.ipynb')
    );
});