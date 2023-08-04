import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/image_gen_craiyon.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/image_gen_craiyon.ipynb')
    );
});