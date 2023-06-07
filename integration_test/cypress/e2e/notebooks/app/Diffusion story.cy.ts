import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Diffusion story.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Diffusion story.ipynb')
    );
});