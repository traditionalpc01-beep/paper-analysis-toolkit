import React, { useState, useCallback, useRef } from 'react';

const DropZone = React.memo(function DropZone({
  onFilesSelected,
  accept = '.pdf',
  multiple = true,
  disabled = false,
  maxFiles = 50,
  maxSizeMB = 100
}) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [error, setError] = useState('');
  const [dragCounter, setDragCounter] = useState(0);
  const inputRef = useRef(null);

  const validateFiles = useCallback((files) => {
    const validFiles = [];
    const errors = [];

    const maxSize = maxSizeMB * 1024 * 1024;

    Array.from(files).forEach((file) => {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        errors.push(`"${file.name}" 不是 PDF 文件`);
        return;
      }

      if (file.size > maxSize) {
        errors.push(`"${file.name}" 超过 ${maxSizeMB}MB 限制`);
        return;
      }

      validFiles.push(file);
    });

    if (validFiles.length > maxFiles) {
      errors.push(`文件数量超过 ${maxFiles} 个限制，已选取前 ${maxFiles} 个`);
      return {
        validFiles: validFiles.slice(0, maxFiles),
        errors
      };
    }

    return { validFiles, errors };
  }, [maxFiles, maxSizeMB]);

  const handleFiles = useCallback((files) => {
    setError('');

    if (!files || files.length === 0) {
      return;
    }

    const { validFiles, errors } = validateFiles(files);

    if (errors.length > 0) {
      setError(errors.join('；'));
    }

    if (validFiles.length > 0 && onFilesSelected) {
      onFilesSelected(validFiles);
    }
  }, [validateFiles, onFilesSelected]);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled) return;

    setDragCounter((prev) => prev + 1);
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragActive(true);
    }
  }, [disabled]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled) return;

    setDragCounter((prev) => {
      const newCount = prev - 1;
      if (newCount === 0) {
        setIsDragActive(false);
      }
      return newCount;
    });
  }, [disabled]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled) return;

    e.dataTransfer.dropEffect = 'copy';
  }, [disabled]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (disabled) return;

    setIsDragActive(false);
    setDragCounter(0);

    const files = e.dataTransfer.files;
    handleFiles(files);
  }, [disabled, handleFiles]);

  const handleClick = useCallback(() => {
    if (disabled) return;
    inputRef.current?.click();
  }, [disabled]);

  const handleInputChange = useCallback((e) => {
    const files = e.target.files;
    handleFiles(files);
    e.target.value = '';
  }, [handleFiles]);

  const handleKeyDown = useCallback((e) => {
    if (disabled) return;

    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      inputRef.current?.click();
    }
  }, [disabled]);

  return (
    <div className="dropzone-wrapper">
      <div
        className={`dropzone ${isDragActive ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="拖拽或点击上传 PDF 文件"
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleInputChange}
          style={{ display: 'none' }}
          disabled={disabled}
        />

        <div className="dropzone-content">
          <div className="dropzone-icon">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>

          <div className="dropzone-text">
            {isDragActive ? (
              <strong>松开鼠标上传文件</strong>
            ) : (
              <>
                <strong>拖拽 PDF 文件到此处</strong>
                <span>或点击选择文件</span>
              </>
            )}
          </div>

          <div className="dropzone-hint">
            支持 {multiple ? '多文件' : '单文件'}上传，单个文件最大 {maxSizeMB}MB
          </div>
        </div>
      </div>

      {error && (
        <div className="dropzone-error">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
          <button
            className="dropzone-error-close"
            onClick={() => setError('')}
            aria-label="关闭错误提示"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
});

export default DropZone;
