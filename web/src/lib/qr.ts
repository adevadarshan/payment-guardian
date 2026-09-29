// lib/qr.ts — client QR helpers: pre-checks + preview decode (Slice 3).
// Preview only. The server re-decodes every upload; its verdict is authoritative.
import jsqr from 'jsqr';

export const QR_MAX_BYTES = 5 * 1024 * 1024;

export function checkImageFile(file: File): string | null {
  if (!file.type.startsWith('image/')) return 'Only image files can be scanned as QR codes.';
  if (file.size > QR_MAX_BYTES) return 'Image exceeds the 5 MB limit.';
  return null;
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    if (file.size > QR_MAX_BYTES) {
      reject(new Error('Image exceeds the 5 MB limit.'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result || '');
      const comma = url.indexOf(',');
      resolve(comma >= 0 ? url.slice(comma + 1) : url);
    };
    reader.onerror = () => reject(new Error('Could not read the file.'));
    reader.readAsDataURL(file);
  });
}

/** Best-effort client preview decode. Returns null on any failure. */
export function decodePreview(dataUrl: string): Promise<string | null> {
  return new Promise((resolve) => {
    try {
      const img = new Image();
      img.onload = () => {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          const ctx = canvas.getContext('2d', { willReadFrequently: true });
          if (!ctx) {
            resolve(null);
            return;
          }
          ctx.drawImage(img, 0, 0);
          const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
          const code = jsqr(data.data, data.width, data.height);
          resolve(code ? code.data : null);
        } catch {
          resolve(null);
        }
      };
      img.onerror = () => resolve(null);
      img.src = dataUrl;
    } catch {
      resolve(null);
    }
  });
}
