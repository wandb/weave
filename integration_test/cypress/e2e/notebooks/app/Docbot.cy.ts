import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/app/Docbot.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/app/Docbot.ipynb')
    );
});