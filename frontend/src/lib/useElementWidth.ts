import { useEffect, useRef, useState } from "react";

// Recharts' <ResponsiveContainer> measures its parent via a ResizeObserver
// internally, but was observed rendering a zero-size (empty) chart on first
// paint inside a CSS Grid item in this app — width="100%" doesn't always
// resolve before the first render, and no resize event fires afterward to
// correct it since the grid item's size never actually changes. Measuring
// the container ourselves and passing a real pixel width to a fixed-size
// chart sidesteps that entirely.
export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w) setWidth(w);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, width };
}
