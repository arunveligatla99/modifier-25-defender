/**
 * Analyze page placeholder.
 *
 * Real implementation lands in T145; this file exists so that `npm run dev`
 * starts cleanly during scaffolding without an empty-import error.
 */
export function AnalyzePage(): JSX.Element {
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-2xl font-semibold">Modifier 25 Defender</h1>
      <p className="mt-2 text-slate-600">
        UI placeholder. Implementation lands in T139..T147 of tasks.md.
      </p>
    </main>
  );
}
