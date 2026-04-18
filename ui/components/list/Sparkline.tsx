export function Sparkline({
  values,
  width = 80,
  height = 16,
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
}) {
  const vals = values.filter((v): v is number => v !== null);
  if (vals.length < 2) {
    return <span className="inline-block h-4 w-20 text-muted">—</span>;
  }
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = v === null
      ? height / 2
      : height - ((v - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = values[values.length - 1];
  const trending = vals.length > 1 ? vals[vals.length - 1] - vals[0] : 0;
  const color = trending < 0 ? '#dc2626' : '#16a34a';
  return (
    <svg width={width} height={height} className="align-middle">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        points={pts.join(' ')}
      />
      {last !== null && (
        <circle
          cx={width}
          cy={height - ((last - min) / span) * height}
          r="1.5"
          fill={color}
        />
      )}
    </svg>
  );
}
