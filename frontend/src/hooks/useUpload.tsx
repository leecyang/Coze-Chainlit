import { useCallback } from 'react';
import {
  DropzoneOptions,
  FileRejection,
  FileWithPath,
  useDropzone
} from 'react-dropzone';

import type { FileSpec } from 'client-types/';

interface useUploadProps {
  onError?: (error: string) => void;
  onResolved: (payloads: FileWithPath[]) => void;
  options?: DropzoneOptions;
  spec: FileSpec;
}

const isValidDropzoneMime = (value: string) => {
  if (value === '*/*') return false;
  if (/^(image|audio|video|text)\/\*$/.test(value)) return true;
  return /^[^\s/]+\/(?!\*)[^\s/]+$/.test(value);
};

const useUpload = ({ onError, onResolved, options, spec }: useUploadProps) => {
  const onDrop: DropzoneOptions['onDrop'] = useCallback(
    (acceptedFiles: FileWithPath[], fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        if (fileRejections[0].errors[0].code === 'file-too-large') {
          onError?.(`File is larger than ${spec.max_size_mb} MB`);
        } else {
          onError?.(fileRejections[0].errors[0].message);
        }
      }

      if (!acceptedFiles.length) return;
      return onResolved(acceptedFiles);
    },
    [spec]
  );

  let dzAccept: Record<string, string[]> | undefined;
  const accept = spec.accept;

  if (Array.isArray(accept)) {
    const normalizedAccept: Record<string, string[]> = {};

    accept.forEach((a) => {
      if (typeof a === 'string' && isValidDropzoneMime(a)) {
        normalizedAccept[a] = [];
      }
    });

    if (Object.keys(normalizedAccept).length > 0) {
      dzAccept = normalizedAccept;
    }
  } else if (typeof accept === 'object' && Object.keys(accept).length > 0) {
    const normalizedAccept = Object.fromEntries(
      Object.entries(accept).filter(([mime]) => isValidDropzoneMime(mime))
    );

    if (Object.keys(normalizedAccept).length > 0) {
      dzAccept = normalizedAccept;
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: spec.max_files || undefined,
    accept: dzAccept,
    maxSize: (spec.max_size_mb || 2) * 1000000,
    ...options
  });

  return { getInputProps, getRootProps, isDragActive };
};

export { useUpload };
