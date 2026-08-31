interface StatTileProps {
  label: string;
  value: string;
}

export function StatTile({ label, value }: StatTileProps) {
  return (
    <div className="rounded-[22px] border border-white/80 bg-white/[0.62] p-5 shadow-glass">
      <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-600">{label}</p>
      <p className="mt-2.5 text-[26px] font-bold tracking-tight text-ink-900">{value}</p>
    </div>
  );
}
