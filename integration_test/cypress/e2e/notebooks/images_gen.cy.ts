import {checkWeaveNotebookOutputs} from './notebooks';

describe('../examples/images_gen.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/images_gen.ipynb')
    );
});