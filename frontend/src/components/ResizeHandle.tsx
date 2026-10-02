import { useRef, type KeyboardEvent, type PointerEvent } from "react";

interface Props {
  /** Which panel the handle resizes: the left rail (handle on its right edge) or the right rail. */
  side: "left" | "right";
  width: number;
  min: number;
  max: number;
  defaultWidth: number;
  onWidth: (width: number) => void;
  label: string;
}

const KEY_STEP = 24;

/**
 * Drag handle on the inner edge of a sidebar (also usable with the arrow keys; double-click
 * resets). The width lives in React state only: nothing is stored in the browser.
 */
export function ResizeHandle({ side, width, min, max, defaultWidth, onWidth, label }: Props) {
  const drag = useRef<{ x: number; width: number } | null>(null);
  const clamp = (value: number) => Math.round(Math.min(max, Math.max(min, value)));
  const direction = side === "left" ? 1 : -1;

  function down(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { x: event.clientX, width };
    document.body.classList.add("is-resizing");
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    onWidth(clamp(drag.current.width + direction * (event.clientX - drag.current.x)));
  }
  function up(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    drag.current = null;
    event.currentTarget.releasePointerCapture(event.pointerId);
    document.body.classList.remove("is-resizing");
  }
  function key(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.key === "ArrowRight" ? KEY_STEP : event.key === "ArrowLeft" ? -KEY_STEP : 0;
    if (step) {
      event.preventDefault();
      onWidth(clamp(width + direction * step));
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      onWidth(event.key === "Home" ? min : max);
    }
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={width}
      aria-valuemin={min}
      aria-valuemax={max}
      tabIndex={0}
      title={`${label} (drag, or use the arrow keys; double-click to reset)`}
      className="resize-handle"
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
      onKeyDown={key}
      onDoubleClick={() => onWidth(defaultWidth)}
    />
  );
}
