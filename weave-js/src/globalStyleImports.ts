/**
 * Legacy (global) stylesheets can sometimes have impacts outside of their intended
 * import area, which can cause styling regressions when code-splitting, due to
 * either missing or mis-ordered styles.
 *
 * To make sure stylesheets always load -- and always load in the right order --
 * move them into this file, which is always imported immediately at app load.
 */

import '@wandb/weave/css/wandbTailwindPreflight.css';
import '@wandb/weave/css/index.css';
import '@wandb/weave/common/assets/careyfont/css/careyfont-embedded.css';
import '@wandb/weave/common/components/JupyterViewer.css';
import '@wandb/weave/common/components/Tags/Tags.less';
import '@wandb/weave/common/components/elements/Toast.css';
import '@wandb/weave/common/css/Base.less';
import '@wandb/weave/common/css/DragDrop.less';
import '@wandb/weave/common/css/EditableField.less';
import '@wandb/weave/common/css/Markdown.less';
import '@wandb/weave/common/css/NumberInput.less';
import '@wandb/weave/common/index.css';
import '@wandb/weave/components/Panel2/PanelTable/baseTable.css';
import '@wandb/weave/css/ControlBox.less';
import 'katex/dist/katex.css';
import 'react-base-table/styles.css';
import 'react-datetime/css/react-datetime.css';
import 'react-resizable/css/styles.css';
import 'react-toastify/dist/ReactToastify.min.css';
import '@wandb/semantic/semantic.min.css';
import '@wandb/weave/common/css/SemanticOverride.less';
import '@wandb/weave/common/css/TableEditor.less';
