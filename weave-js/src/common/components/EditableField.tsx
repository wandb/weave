import * as _ from 'lodash';
import React from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import {Form, Header, Icon, Input} from 'semantic-ui-react';

import {linkify} from '../util/links';
import {removeUrlProtocolPrefix} from '../util/url';
import {LegacyWBIcon} from './elements/LegacyWBIcon';

export interface EditableFieldProps {
  icon?: string;
  label?: string;
  value: string;
  /* updateValue defaults to false. It is an unfortunate hack that we added because
  this component wasn't originally designed to handle updates to the "value" prop.
  A lot of the code that uses EditableField doesn't correctly update "value" when
  the user saves local modifications. Ideally we'll fix all that code, then get
  rid of updateValue when it's safe to behave as if it's always true.
  */
  updateValue?: boolean;
  displayValue?: string;
  placeholder: string;
  readOnly?: boolean;
  multiline?: boolean;
  type?: string;
  autoSelect?: boolean;
  maxLength?: number;
  asHeader?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
  className?: string;
  showEditIcon?: boolean;
  renderLinks?: boolean;
  save?(value: string): void;
  /* onFinish is called when the user finishes editing the field. In contrast to
  `save` which is called at a 500ms debounce rate for all edits, `finish` is called
  only when the editing state is exited. This should only be used when you are fine
  with losing the edit-state in the event of network issue or other fatal issue that
  might occur between editing and finishing the edit (eg. browser refresh / close)*/
  onFinish?(value: string): void;
  overrideClick?(): void;
}

interface EditableFieldState {
  editing: boolean;
  origValue: string;
  currentValue: string;
}

/**
 * Generic component for any editable text.
 *
 * Feel free to add support for more types, but please keep it
 * generic, responsive, and compatible with different props
 * and less mixin parameters.
 */
export default class EditableField extends React.Component<
  EditableFieldProps,
  EditableFieldState
> {
  static getDerivedStateFromProps(props: any, state: any) {
    // Hack. See the documentation for props.updateValue in EditableFieldProps above.
    if (!props.updateValue) {
      return null;
    } else {
      if (state.editing) {
        return {
          origValue: props.value,
        };
      } else {
        return {
          origValue: props.value,
          currentValue: props.value,
        };
      }
    }
  }

  state = {
    editing: false,
    origValue: this.props.value,
    currentValue: this.props.value,
  };
  inputRef = React.createRef<Input>();

  save = _.debounce((val: string) => {
    if (this.props.save) {
      this.props.save(val);
    }
  }, 500);

  startEditing = (e: React.SyntheticEvent) => {
    if (this.props.readOnly) {
      return;
    }

    if (this.props.overrideClick) {
      this.props.overrideClick();
      return;
    }

    e.stopPropagation();
    e.preventDefault();

    this.setState({editing: true}, () => {
      if (
        (this.props.autoSelect == null || this.props.autoSelect) &&
        this.inputRef.current
      ) {
        this.inputRef.current.select();
      }
    });
  };

  stopEditing = () => {
    this.setState({editing: false, origValue: this.state.currentValue});
    this.save.flush();
    this.props.onFinish?.(this.state.currentValue);
  };

  cancelEditing = () => {
    this.setState({editing: false, currentValue: this.state.origValue});
    this.save(this.state.origValue);
    this.save.flush();
  };

  onKeyDown = (e: any) => {
    if (e.keyCode === 27) {
      this.cancelEditing();
      return;
    }
    if (e.keyCode === 13) {
      this.stopEditing();
    }
  };

  onKeyDownMultiline = (e: any) => {
    if (e.keyCode === 27) {
      this.cancelEditing();
    }
    if (e.keyCode === 13 && e.shiftKey) {
      this.stopEditing();
    }
  };

  updateValue = (v: string) => {
    this.setState({currentValue: v});
    this.save(v);
  };

  render() {
    const className = `editable-field ${this.props.className || ''} ${
      this.props.type === 'url' ? 'url' : ''
    } ${this.props.readOnly ? 'read-only' : ''}`;
    const fieldClassName = `field-content${
      this.state.currentValue ? '' : ' placeholder'
    }`;

    if (this.props.readOnly && !this.state.currentValue) {
      return <></>;
    }

    let fieldComponent: JSX.Element;
    if (this.state.editing) {
      if (this.props.multiline) {
        fieldComponent = (
          <Form>
            <Form.TextArea
              autoFocus
              rows="2"
              minRows={2}
              maxLength={this.props.maxLength}
              value={this.state.currentValue}
              onChange={e => this.updateValue(e.currentTarget.value)}
              onKeyDown={this.onKeyDownMultiline}
              placeholder={this.props.placeholder}
              onBlur={this.stopEditing}
              control={TextareaAutosize}
            />
          </Form>
        );
      } else {
        // Not multiline.
        fieldComponent = (
          <Input
            type={this.props.type || 'text'}
            autoFocus
            value={this.state.currentValue}
            maxLength={this.props.maxLength}
            onChange={e => {
              let newVal = e.currentTarget.value;
              if (this.props.type === 'url') {
                newVal = removeUrlProtocolPrefix(newVal);
              }
              this.updateValue(newVal);
            }}
            placeholder={this.props.placeholder}
            onKeyDown={this.onKeyDown}
            ref={this.inputRef}
            onBlur={this.stopEditing}
          />
        );
      }
    } else {
      // Not editing, just displaying value.
      let renderableValue: string | ReturnType<typeof linkify> =
        this.props.displayValue || this.state.currentValue;
      if (
        this.props.type !== 'url' &&
        !_.isEmpty(renderableValue) &&
        this.props.renderLinks
      ) {
        renderableValue = linkify(renderableValue, {
          onClick: e => e.stopPropagation(),
        });
      }
      const subComponents: JSX.Element[] = [];
      if (this.props.asHeader) {
        subComponents.push(
          <Header
            key={fieldClassName}
            className={fieldClassName}
            as={this.props.asHeader}>
            {renderableValue || this.props.placeholder}
          </Header>
        );
      } else {
        subComponents.push(
          <span key={fieldClassName} className={fieldClassName}>
            {renderableValue || this.props.placeholder}
          </span>
        );
      }
      if (this.props.type === 'url' && renderableValue) {
        subComponents.push(
          <LegacyWBIcon
            key="link-icon"
            className="goto-link-icon"
            name="launch"
            onClick={() => {
              // eslint-disable-next-line wandb/no-unprefixed-urls
              window.open(
                'http://' + this.state.currentValue,
                '_blank',
                'noopener'
              );
            }}
          />
        );
      }

      if (this.props.showEditIcon) {
        subComponents.push(<LegacyWBIcon key="edit-icon" name="edit" />);
      }

      fieldComponent = <>{subComponents}</>;
    }

    return (
      <div
        className={className}
        onClick={
          this.state.editing
            ? e => {
                e.preventDefault();
                e.stopPropagation();
              }
            : e => this.startEditing(e)
        }>
        {this.props.icon && (
          <Icon className={`label-icon ${this.props.icon}`} />
        )}
        {this.props.label && <label>{this.props.label}</label>}
        {fieldComponent}
      </div>
    );
  }
}
