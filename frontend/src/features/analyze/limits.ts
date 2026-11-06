export const MAX_INPUT_BYTES = 204_800;

const encoder = new TextEncoder();

export function utf8Bytes(text: string): number {
  return encoder.encode(text).length;
}

export function formatKb(bytes: number): string {
  const kb = bytes / 1024;
  return kb >= 10 || kb === 0 ? `${Math.round(kb)} KB` : `${kb.toFixed(1)} KB`;
}
