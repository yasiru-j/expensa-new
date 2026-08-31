export function AuthHeader() {
  return (
    <div className="flex items-center justify-between px-6 py-6 sm:px-8">
      <div className="flex items-center gap-2.5">
        <img
          src="/expensa-logo.png"
          alt=""
          className="h-[34px] w-[34px] rounded-[10px] object-cover shadow-brand"
        />
        <span className="text-lg font-extrabold tracking-tight text-ink-900">Expensa</span>
      </div>
      <div className="hidden font-mono text-[11px] uppercase tracking-[0.14em] text-ink-600 sm:block">
        AI powered expense logger
      </div>
    </div>
  );
}
