import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/image_gen_craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/image_gen_craiyon.ipynb')
    );
});