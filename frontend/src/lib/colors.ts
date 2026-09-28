/** Colour-vision-safe categorical palette (fixed slot order) for entity types. */
export const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

export type ColorMap = Record<string, string>;

/** Assign palette slots to labels in the given order (most frequent first). */
export function colorMap(labels: string[]): ColorMap {
  const map: ColorMap = {};
  labels.forEach((label, i) => {
    map[label] = PALETTE[i % PALETTE.length];
  });
  return map;
}

export function colorOf(map: ColorMap, label: string): string {
  return map[label] ?? "#6a707a";
}

export function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
