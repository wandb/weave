import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../examples/control/Slider.ipynb notebook test', () => {
    it('passes', () =>
        checkWeaveNotebookOutputs('../examples/control/Slider.ipynb')
    );
});