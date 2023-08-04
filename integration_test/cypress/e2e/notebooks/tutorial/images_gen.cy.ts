import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/tutorial/images_gen.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/tutorial/images_gen.ipynb')
    );
});