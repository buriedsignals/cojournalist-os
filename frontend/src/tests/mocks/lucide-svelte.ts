// vitest mock for lucide-svelte — tests don't render Svelte, so any
// placeholder identity works. Pure utility tests in src/tests/utils/
// import icon config transitively via $lib/utils/scouts.ts.
const Icon = (() => ({})) as unknown;
export const Globe = Icon;
export const Radar = Icon;
export const Users = Icon;
export const Landmark = Icon;
