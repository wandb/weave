import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/reference/control/Object Picker.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/reference/control/Object Picker.ipynb')
    );
});