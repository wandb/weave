import Tooltip from '@mui/material/Tooltip';
import * as _ from 'lodash';
import numeral from 'numeral';
import Prism from 'prismjs';
import React, {FC, useCallback, useEffect, useRef, useState} from 'react';
import TimeAgo from 'react-timeago';
import {Header, Icon, Pagination, Segment, Table} from 'semantic-ui-react';

import getConfig from '../../config';
import * as globals from '../css/globals.styles';
import {TargetBlank} from '../util/links';
import * as NetronUtils from '../util/netron';
import {encodeURIPercentChar, parseRunTabPath} from '../util/url';
import BasicNoMatchComponent from './BasicNoMatchComponent';
import {LegacyWBIcon} from './elements/LegacyWBIcon';
import * as S from './FileBrowser.styles';
import JupyterViewerFromRunFile from './JupyterViewer';
import Markdown from './Markdown';
import Loader from './WandbLoader';

const FILE_EXPORT_DOC_URL =
  'https://docs.wandb.ai/library/public-api-guide#download-all-files-from-a-run';
const MAX_NUM_FILES = 10000;

/*
  This will soon be replaced by the Panels2 file browser, much of this logic
  is duplicated in StorageFileBrowser.
*/

interface Node {
  files: FileData[];
  subdirectories: {[key: string]: Node};
}

export interface FileData {
  id: string;
  name: string;
  url?: string | null;
  sizeBytes: number;
  // Run files always passes updatedAt, ArtifactFiles never does (individual
  // file timestamps aren't very useful for artifacts)
  updatedAt?: Date | null;

  // ArtifactFiles may pass either of these, or both
  ref?: string;
  digest?: string;

  storagePolicyConfig?: {
    storageRegion?: string;
    storageLayout?: string;
  };
}

// takes a flat array of file objects and converts it into a nested object, based on filenames
function makeFileTree(filesArray: FileData[]): Node {
  const fileTree: Node = {files: [], subdirectories: {}};
  filesArray.forEach(file => {
    let currentFolder = fileTree;
    // 'media/images/image01.jpg' => ['media','images','image01.jpg']
    const path = file.name.split('/');
    while (path.length > 1) {
      // The following is safe to do because we made sure path had elems in the loop condition.
      const folderName = path.shift() as string;
      // create subfolder if it doesn't already exist
      if (!currentFolder.subdirectories[folderName]) {
        currentFolder.subdirectories[folderName] = {
          files: [],
          subdirectories: {},
        };
      }
      currentFolder = currentFolder.subdirectories[folderName];
    }
    // if we've come to the last item in the path, add this file object to the current folder
    currentFolder.files.push(file);
  });
  return fileTree;
}

type PreviewTypes =
  | 'netron'
  | 'image'
  | 'markdown'
  | 'code'
  | 'notebook'
  | 'artifact'
  | 'unknown';

interface FileInfo {
  type: PreviewTypes;
  fullScreen?: boolean;

  language?: string;
  iconName: string;
}

export function fileInfoFromName(fileName: string): FileInfo {
  if (NetronUtils.isViewable(fileName)) {
    return {type: 'netron', fullScreen: true, iconName: 'file-model'};
  }
  if (fileName.match(/:v\d+$/)) {
    // TODO: nice artifact icon
    return {type: 'artifact', iconName: 'file'};
  }

  const extension = fileName.split('.').pop();
  switch (extension) {
    case 'md':
      return {
        iconName: 'file-markdown',
        type: 'markdown',
      };
    case 'log':
    case 'text':
    case 'txt':
      return {
        iconName: 'file',
        type: 'code',
      };
    case 'patch':
      return {
        iconName: 'file-code',
        type: 'code',
        language: 'diff',
      };
    case 'py':
      return {
        iconName: 'file-python',
        type: 'code',
        language: 'python',
      };
    case 'ipynb':
      return {
        iconName: 'file-python',
        type: 'notebook',
        language: 'python',
      };
    case 'yml':
    case 'yaml':
      return {
        iconName: 'file-yaml',
        type: 'code',
        language: 'yaml',
      };
    case 'xml':
      return {
        iconName: 'file-yaml',
        type: 'code',
        language: 'xml',
      };
    case 'html':
    case 'htm':
      return {
        iconName: 'file-yaml',
        type: 'code',
        language: 'html',
      };
    case 'sh':
    case 'json':
    case 'css':
    case 'js':
      return {
        iconName: 'file-code',
        type: 'code',
        language: extension,
      };
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'tiff':
    case 'tif':
    case 'gif':
      return {type: 'image', iconName: 'file-image'};
  }
  return {type: 'unknown', iconName: 'file'};
}

// Maybe we should move this to requests?
export type UseLoadFile = (
  file: FileData,
  options: {
    onSuccess?: (response: any) => void;
    onFailure?: () => void;
    fallback?: () => void;
  }
) => boolean;

export type UseLoadFileUrl = (
  file: FileData
) => {loading: true} | {loading: false; file: {directUrl: string} | undefined};

interface FileBrowserProps {
  totalFiles: number;
  isCodeHidden?: boolean;
  files: FileData[];
  path?: string;
  history: any;

  useLoadFile: UseLoadFile;
  useLoadFileUrl: UseLoadFileUrl;
  setFilePath(path: string[]): void;
}

const PAGE_SIZE = 25;

const FileBrowser: FC<FileBrowserProps> = ({
  files,
  isCodeHidden,
  path,
  setFilePath,
  totalFiles,
  useLoadFile,
  useLoadFileUrl,
}) => {
  const filePath = parseRunTabPath(path);
  const pathString = filePath.join('/');
  let currentFolder: Node | undefined = makeFileTree(files);
  // traverse the tree to the current directory
  let currentFile: FileData | undefined;
  let preview: JSX.Element | undefined;
  filePath.forEach(folderName => {
    if (currentFolder == null) {
      preview = <Segment textAlign="center">No such file!</Segment>;
      return;
    }
    if (currentFolder.subdirectories[folderName] != null) {
      currentFolder = currentFolder.subdirectories[folderName];
    } else {
      currentFile = currentFolder.files.find(f => f.name === pathString);
      currentFolder = undefined;
      if (currentFile == null) {
        preview = <Segment textAlign="center">No such file!</Segment>;
        return;
      }
    }
  });

  if (currentFile != null) {
    const info = fileInfoFromName(currentFile.name);
    preview = (
      <Preview
        useLoadFile={useLoadFile}
        useLoadFileUrl={useLoadFileUrl}
        file={currentFile}
        fileInfo={info}
      />
    );
    if (info.fullScreen) {
      return preview;
    }
  }

  return (
    <div className="file-browser">
      {totalFiles > MAX_NUM_FILES && (
        <p style={{fontStyle: 'italic'}}>
          <Icon name="warning sign" style={{marginRight: '5px'}} />
          {`File view is truncated to the first ${MAX_NUM_FILES} files. To view the rest, use our`}{' '}
          <TargetBlank href={FILE_EXPORT_DOC_URL}>
            Python file export API.
          </TargetBlank>
        </p>
      )}
      {/* render the path */}
      <Header className="file-browser-path">
        &gt;&nbsp;
        {['root'].concat(filePath).map((folderName, i) => {
          const newPath = filePath.slice(0, i);
          return [
            <span
              className="file-browser-path-item"
              style={{cursor: 'pointer'}}
              key={'path' + i}
              onClick={() => setFilePath(newPath)}>
              {folderName}
            </span>,
            i !== filePath.length ? ' / ' : undefined,
          ];
        })}
        {currentFile != null && (
          <Tooltip title="Download">
            <a
              href={encodeURIPercentChar(currentFile.url!)}
              download={currentFile.name}>
              <LegacyWBIcon
                style={{position: 'relative', top: 2}}
                name="download"
              />
            </a>
          </Tooltip>
        )}
      </Header>
      {currentFolder != null && (
        <Folder
          useLoadFile={useLoadFile}
          folder={currentFolder}
          path={filePath}
          isCodeHidden={isCodeHidden}
          setFilePath={setFilePath}
        />
      )}
      {preview}
    </div>
  );
};

export default FileBrowser;

interface FolderData {
  subdirectories: {[name: string]: FolderData};
  files: FileData[];
}

interface FolderProps {
  useLoadFile: UseLoadFile;
  folder: FolderData;
  path: string[];
  isCodeHidden?: boolean;
  setFilePath(path: string[]): void;
}

const Folder: FC<FolderProps> = ({
  useLoadFile,
  folder,
  path,
  isCodeHidden,
  setFilePath,
}) => {
  const [displayOffset, setDisplayOffset] = useState(0);
  const [search, setSearch] = useState('');
  // separate subfolders from files in this directory
  const rootFiles = folder.files;
  const subfolderKeys = Object.keys(folder.subdirectories).sort();
  if (isCodeHidden) {
    _.remove(rootFiles, f => f.name.indexOf('.patch') > -1);
    _.remove(subfolderKeys, f => f === 'code');
  }

  const foldersAndFiles = [...subfolderKeys, ...rootFiles].filter(
    folderOrFile => {
      const match = search.toLowerCase().trim();
      if (typeof folderOrFile === 'string') {
        return folderOrFile.toLowerCase().indexOf(match) !== -1;
      }

      return folderOrFile.name.toLowerCase().indexOf(match) !== -1;
    }
  );
  return (
    <>
      <Table unstackable selectable className="file-browser-table">
        <S.FileTableBody>
          <S.SearchRow>
            <td colSpan={10}>
              <SearchInput value={search} onChange={setSearch} />
            </td>
          </S.SearchRow>
          {foldersAndFiles.length === 0 && (
            <S.NoResultsRow>
              <S.NoResultsMessage>No files matching search</S.NoResultsMessage>
            </S.NoResultsRow>
          )}
          {foldersAndFiles
            .slice(displayOffset, displayOffset + PAGE_SIZE)
            .map(folderOrFile => {
              if (_.isString(folderOrFile)) {
                return (
                  <SubFolder
                    key={'folder-' + folderOrFile}
                    folder={folder.subdirectories[folderOrFile]}
                    folderName={folderOrFile}
                    path={path}
                    setFilePath={setFilePath}
                  />
                );
                // return this.renderSubFolder(currentFolder, folderOrFile, i);
              } else {
                return (
                  <File
                    key={'file-' + folderOrFile.name}
                    useLoadFile={useLoadFile}
                    file={folderOrFile}
                    path={path}
                    setFilePath={setFilePath}
                  />
                );
              }
            })}
        </S.FileTableBody>
      </Table>
      {foldersAndFiles.length > PAGE_SIZE && (
        <div style={{display: 'flex', justifyContent: 'center'}}>
          <Pagination
            defaultActivePage={1}
            totalPages={Math.ceil(foldersAndFiles.length / PAGE_SIZE)}
            onPageChange={(e, data) => {
              const pg = data.activePage;
              if (pg != null && _.isNumber(pg)) {
                setDisplayOffset((pg - 1) * PAGE_SIZE);
              }
            }}
            size="small"
          />
        </div>
      )}
    </>
  );
};

interface SubFolderProps {
  folder: FolderData;
  path: string[];
  folderName: string;
  setFilePath(path: string[]): void;
}

const SubFolder: FC<SubFolderProps> = ({
  folder,
  folderName,
  path,
  setFilePath,
}) => {
  const subFolderCount = Object.keys(folder.subdirectories).length;
  const fileCount = folder.files.length;
  const newPath = path.concat([folderName]);
  return (
    <Table.Row
      className="file-browser-folder"
      onClick={() => setFilePath(newPath)}>
      <Table.Cell className="folder-name-cell">
        <div className="file-browser-name-cell-wrapper">
          <LegacyWBIcon className="file-browser-icon" name="folder" />
          <span className="file-browser-folder-name">{folderName}</span>
          &nbsp;/
        </div>
      </Table.Cell>
      <Table.Cell className="contents-cell">
        {subFolderCount !== 0 &&
          subFolderCount +
            (subFolderCount === 1 ? ' subfolder, ' : ' subfolders, ')}
        {fileCount + (fileCount === 1 ? ' file' : ' files')}
      </Table.Cell>
      <Table.Cell className="hide-in-mobile" />
      <Table.Cell className="hide-in-mobile" />
    </Table.Row>
  );
};

interface FileProps {
  file: FileData;
  path: string[];
  useLoadFile: UseLoadFile;
  setFilePath(path: string[]): void;
}

const File: FC<FileProps> = ({file, path, setFilePath}) => {
  const fileName = file.name.split('/').pop() || '';
  const newPath = path.concat([fileName]);
  const fileInfo = fileInfoFromName(fileName);
  const iconName = fileInfo.iconName;

  return (
    <Table.Row
      onClick={() => {
        if (file.ref == null) {
          setFilePath(newPath);
        } else if (
          file.ref.startsWith('http://') ||
          file.ref.startsWith('https://')
        ) {
          window.open(file.ref);
        }
      }}>
      <Table.Cell className="file-name-cell">
        <div className="file-browser-name-cell-wrapper">
          {file.ref != null ? (
            <Icon
              style={{color: globals.primary, width: 28}}
              name="arrow alternate circle right outline"
            />
          ) : (
            <LegacyWBIcon className="file-browser-icon" name={iconName} />
          )}
          <span className="file-browser-file-name">
            {file.name.split('/').pop()}
          </span>
        </div>
      </Table.Cell>
      <Table.Cell className="updated-time-cell">
        {file.ref != null ? (
          file.ref
        ) : file.updatedAt != null ? (
          <TimeAgo date={file.updatedAt + 'Z'} />
        ) : undefined}
      </Table.Cell>
      <Table.Cell className="file-size-cell">
        {numeral(file.sizeBytes).format('0.0b')}
      </Table.Cell>
      <Table.Cell>
        <Tooltip title="Download">
          <a
            href={file.ref != null ? file.ref : encodeURIPercentChar(file.url!)}
            download={file.name}
            onClick={e => e.stopPropagation()}>
            <LegacyWBIcon name="download" />
          </a>
        </Tooltip>
      </Table.Cell>
    </Table.Row>
  );
};

interface PreviewProps {
  useLoadFile: UseLoadFile;
  useLoadFileUrl: UseLoadFileUrl;
  file: FileData;
  fileInfo: FileInfo;
}

const Preview: FC<PreviewProps> = ({
  useLoadFile,
  useLoadFileUrl,
  file,
  fileInfo,
}) => {
  const fileType = fileInfo.type;
  if (fileType === 'image') {
    return <img alt={file.name} src={file.url!} />;
  } else if (fileType === 'code') {
    return (
      <CodePreview
        useLoadFile={useLoadFile}
        file={file}
        language={fileInfo.language}
      />
    );
  } else if (fileType === 'notebook') {
    return <JupyterViewerFromRunFile useLoadFile={useLoadFile} file={file} />;
  } else if (fileType === 'unknown') {
    return (
      <div>
        File type unknown,
        <a href={encodeURIPercentChar(file.url!)} download={file.name}>
          {' '}
          click here
        </a>{' '}
        to download.
      </div>
    );
  } else if (fileType === 'netron') {
    return <Netron useLoadFileUrl={useLoadFileUrl} file={file} />;
  } else if (fileType === 'markdown') {
    return <MarkdownPreview useLoadFile={useLoadFile} file={file} />;
  } else {
    return (
      <div>
        Invalid file type,
        <a href={encodeURIPercentChar(file?.url ?? '#')} download={file?.name}>
          {' '}
          click here
        </a>{' '}
        to attempt to download.
      </div>
    );
  }
};

interface NetronProps {
  useLoadFileUrl: UseLoadFileUrl;
  file: FileData;
}

const Netron: FC<NetronProps> = ({useLoadFileUrl, file: fileToQuery}) => {
  // It's tempting to fetch directUrl in the filebrowser files query, but directUrls
  // expire after 60s, so we need to fetch it just in time, right as we render the
  // iframe.
  const query = useLoadFileUrl(fileToQuery);
  const NoMatch = BasicNoMatchComponent;
  if (query.loading) {
    return <Loader name="file-browser" />;
  }
  const file = query.file;
  if (file == null) {
    return <NoMatch />;
  }
  // thirdPartyAnalyticsOK is set by index.html
  const enableTelemetryString = !(window as any).thirdPartyAnalyticsOK
    ? ''
    : '&telemetry=1';
  return (
    <iframe
      style={{width: '100%', height: '100%', border: 'none'}}
      title="Netron preview"
      src={getConfig().urlPrefixed(
        `/netron/index.html?url=${encodeURIComponent(
          file.directUrl
        )}&identifier=${encodeURIComponent(
          fileToQuery.name
        )}${enableTelemetryString}`
      )}
    />
  );
};

interface CodePreviewProps {
  useLoadFile: UseLoadFile;
  file: FileData;

  language?: string;
}

const CodePreview: FC<CodePreviewProps> = ({useLoadFile, file, language}) => {
  const [data, setDataVal] = useState('');
  const [error, setErrorVal] = useState<string | undefined>(undefined);
  const ref = useRef<HTMLDivElement>(null);
  const setData = useCallback(
    (d: string) => {
      // Automatically reformat JSON
      let lines = d.split('\n');
      if (
        (file.name.endsWith('.json') && lines.length === 1) ||
        (lines.length === 2 && lines[1] === '')
      ) {
        try {
          const parsed = JSON.parse(lines[0]);
          lines = JSON.stringify(parsed, undefined, 2).split('\n');
        } catch {
          // ok
        }
      }

      // Truncate long lines
      const truncated = lines
        .map(line => {
          if (line.length > 1000) {
            return line.slice(0, 1000) + ' (line truncated to 1000 characters)';
          } else {
            return line;
          }
        })
        .join('\n');

      setDataVal(truncated);
    },
    [setDataVal, file.name]
  );
  const setError = useCallback(
    (errorString?: string) => setErrorVal(errorString || 'Error loading file'),
    [setErrorVal]
  );

  // We don't pass a fallback to allow dev mode zero byte files to render
  const loading = useLoadFile(file, {
    onSuccess: setData,
    onFailure: setError,
  });
  useEffect(() => {
    if (ref.current != null) {
      Prism.highlightElement(ref.current);
    }
  });
  if (error != null) {
    return <Segment textAlign="center">{error}</Segment>;
  }
  if (loading) {
    return <Loader name="code-preview-loader" />;
  }
  // HACKING TO DISPLAY VOC
  // if (file.name.endsWith('.xml')) {
  //   const parser = new DOMParser();
  //   const xmlDoc = parser.parseFromString(data, 'text/xml');
  //   const anno = xmlDoc.getElementsByTagName('annotation')[0];
  //   if (anno != null) {
  //     for (let i = 0; i < anno.childNodes.length; i++) {
  //       const node = anno.childNodes[i];
  //       if (node.nodeType !== Node.TEXT_NODE && node.nodeName === 'filename') {
  //         const filename = node.childNodes[0].textContent;
  //         console.log('FILE NAME', filename);
  //         // const imageFile = (node as any).getElementsByTagName('filename')[0];
  //         // console.log('IMAGE FILE', imageFile);
  //       }
  //       console.log(node);
  //     }
  //     // anno.childNodes[]
  //     // console.log('VOC!');
  //   }
  // }
  return (
    <div
      style={{
        background: 'white',
        border: '1px solid #eee',
        padding: 16,
      }}>
      <pre
        style={{
          maxWidth: '100%',
        }}>
        <code
          style={{whiteSpace: 'pre-wrap', wordBreak: 'break-all'}}
          ref={ref}
          className={language != null ? `language-${language}` : undefined}>
          {data}
        </code>
      </pre>
    </div>
  );
};

interface MarkdownPreviewProps {
  useLoadFile: UseLoadFile;
  file: FileData;
}

const MarkdownPreview: FC<MarkdownPreviewProps> = ({useLoadFile, file}) => {
  const [data, setData] = useState('');
  const [error, setError] = useState<string | null>(null);

  const onFailure = useCallback((errorString?: string) => {
    setError(errorString || 'Error loading file');
  }, []);
  const loading = useLoadFile(file, {
    onSuccess: setData,
    onFailure,
  });

  if (loading) {
    return <Loader name="markdown-preview-loader" />;
  } else if (error != null) {
    return <Segment textAlign="center">{error}</Segment>;
  } else {
    return (
      <div
        style={{
          background: 'white',
          border: '1px solid #eee',
          padding: 16,
        }}>
        <pre
          style={{
            maxWidth: '100%',
            overflowX: 'hidden',
            textOverflow: 'ellipsis',
          }}>
          <Markdown content={data} />
        </pre>
      </div>
    );
  }
};

const SearchInput = (props: {
  value: string;
  onChange: (newValue: string) => void;
}) => {
  return (
    <S.SearchInputContainer>
      <S.SearchInputIcon name="search" />
      <input
        value={props.value}
        placeholder="Search"
        onChange={e => props.onChange(e.target.value)}
      />
    </S.SearchInputContainer>
  );
};
