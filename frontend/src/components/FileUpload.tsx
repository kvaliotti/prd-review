import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { notionAPI } from '../services/api';
import { PageType } from '../types';

interface FileUploadProps {
  onUploadComplete: () => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete }) => {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [pageTypes, setPageTypes] = useState<Record<string, PageType>>({});

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles(prevFiles => [...prevFiles, ...acceptedFiles]);
    // Set default page type for new files
    const newPageTypes: Record<string, PageType> = {};
    acceptedFiles.forEach(file => {
      newPageTypes[file.name] = PageType.research;
    });
    setPageTypes(prev => ({ ...prev, ...newPageTypes }));
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/markdown': ['.md'],
      'text/plain': ['.txt'],
    },
    multiple: true,
  });

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    const newUploadProgress: Record<string, number> = {};
    
    for (const file of files) {
      newUploadProgress[file.name] = 0;
    }
    setUploadProgress(newUploadProgress);

    for (const file of files) {
      try {
        await notionAPI.uploadFile(
          file, 
          pageTypes[file.name] || PageType.research,
          (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / (progressEvent.total || 1)
            );
            setUploadProgress(prev => ({ ...prev, [file.name]: percentCompleted }));
          }
        );
      } catch (error) {
        console.error(`Error uploading ${file.name}:`, error);
        setUploadProgress(prev => ({ ...prev, [file.name]: -1 }));
      }
    }

    setUploading(false);
    setFiles([]);
    setPageTypes({});
    setUploadProgress({});
    onUploadComplete();
  };
  
  const handleRemoveFile = (fileName: string) => {
    setFiles(files.filter(file => file.name !== fileName));
    const newPageTypes = { ...pageTypes };
    delete newPageTypes[fileName];
    setPageTypes(newPageTypes);
  };
  
  const handlePageTypeChange = (fileName: string, type: PageType) => {
    setPageTypes(prev => ({ ...prev, [fileName]: type }));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getProgressColor = (progress: number): string => {
    if (progress === -1) return '#e74c3c';
    if (progress === 100) return '#27ae60';
    return '#667eea';
  };

  return (
    <div className="kb-card">
      <div className="card-header">
        <span className="card-icon">📁</span>
        <div>
          <h2 className="card-title">File Upload</h2>
          <p className="card-description">Upload documents directly to your knowledge base</p>
        </div>
      </div>

      <div 
        {...getRootProps()} 
        className={`file-dropzone ${isDragActive ? 'active' : ''} ${files.length > 0 ? 'has-files' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="dropzone-content">
          <span className="dropzone-icon">📤</span>
          <p className="dropzone-text">
            {isDragActive 
              ? "Drop the files here..." 
              : "Drag & drop files here, or click to select"
            }
          </p>
          <p className="dropzone-hint">Supports PDF, Markdown (.md), and Text (.txt) files</p>
        </div>
      </div>

      {files.length > 0 && (
        <div className="files-list">
          <h3>Files Ready for Upload</h3>
          {files.map(file => (
            <div key={file.name} className="file-item">
              <div className="file-info">
                <div className="file-name">{file.name}</div>
                <div className="file-size">{formatFileSize(file.size)}</div>
              </div>
              
              <div className="file-controls">
                <select 
                  value={pageTypes[file.name] || PageType.research} 
                  onChange={(e) => handlePageTypeChange(file.name, e.target.value as PageType)}
                  className="file-type-select"
                  disabled={uploading}
                >
                  <option value={PageType.prd}>PRD</option>
                  <option value={PageType.research}>Research</option>
                  <option value={PageType.analytics}>Analytics</option>
                </select>
                
                <button 
                  onClick={() => handleRemoveFile(file.name)}
                  className="btn-remove"
                  disabled={uploading}
                >
                  ✕
                </button>
              </div>

              {uploading && (
                <div className="upload-progress">
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ 
                        width: `${Math.max(0, uploadProgress[file.name] || 0)}%`,
                        backgroundColor: getProgressColor(uploadProgress[file.name] || 0)
                      }}
                    />
                  </div>
                  <span className="progress-text">
                    {uploadProgress[file.name] === -1 
                      ? 'Error' 
                      : uploadProgress[file.name] === 100 
                      ? 'Complete' 
                      : `${uploadProgress[file.name] || 0}%`
                    }
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="upload-actions">
        <button 
          onClick={handleUpload} 
          disabled={files.length === 0 || uploading}
          className="btn-primary"
        >
          {uploading ? 'Uploading...' : `Upload ${files.length} File${files.length !== 1 ? 's' : ''}`}
        </button>
      </div>
    </div>
  );
};

export default FileUpload; 