// Preparação do arquivo antes do envio (spec file-upload).

export const MAX_BYTES = 20 * 1024 * 1024;

function readBytes(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

/** HEIC/HEIF (fotos de iPhone): o servidor não lê; viram JPG aqui no navegador. */
export async function isHeic(file: File): Promise<boolean> {
  if (/image\/hei[cf]/i.test(file.type) || /\.hei[cf]$/i.test(file.name)) return true;
  const head = new Uint8Array(await readBytes(file.slice(4, 12)));
  const brand = String.fromCharCode(...head);
  return /^ftyp(heic|heix|hevc|mif1|msf1)/.test(brand);
}

export async function prepareFile(file: File): Promise<{ blob: Blob; name: string }> {
  if (!(await isHeic(file))) return { blob: file, name: file.name };
  const { default: heic2any } = await import("heic2any");
  const converted = await heic2any({ blob: file, toType: "image/jpeg", quality: 0.92 });
  const blob = Array.isArray(converted) ? converted[0] : converted;
  return { blob, name: file.name.replace(/\.[^.]+$/, "") + ".jpg" };
}
