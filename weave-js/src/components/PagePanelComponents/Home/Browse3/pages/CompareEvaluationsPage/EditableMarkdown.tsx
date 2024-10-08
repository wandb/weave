import React, {useState} from 'react';
import ReactMarkdown from 'react-markdown';
import styled from 'styled-components';

interface EditableMarkdownProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}

export const EditableMarkdown: React.FC<EditableMarkdownProps> = ({
  value,
  onChange,
  placeholder,
}) => {
  const [isEditing, setIsEditing] = useState(false);

  return (
    <Container onDoubleClick={() => setIsEditing(true)}>
      {isEditing ? (
        <TextArea
          value={value}
          onChange={e => onChange(e.target.value)}
          onBlur={() => setIsEditing(false)}
          placeholder={placeholder}
          autoFocus
        />
      ) : (
        <MarkdownContainer>
          <ReactMarkdown>{value || placeholder}</ReactMarkdown>
        </MarkdownContainer>
      )}
    </Container>
  );
};

const Container = styled.div`
  width: 100%;
  min-height: 100px;
`;

const TextArea = styled.textarea`
  width: 100%;
  min-height: 100px;
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: inherit;
  font-size: inherit;
  resize: vertical;
`;

const MarkdownContainer = styled.div`
  cursor: pointer;
  &:hover {
    background-color: #f0f0f0;
  }
`;
