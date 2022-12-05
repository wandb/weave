import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/control/Object Picker.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/control/Object Picker.ipynb')
    );
});