import type { ModelJson, SeasonJson } from "@cutline/sim";
import type { Loaded, Snapshot } from "./types.ts";

const base = import.meta.env.BASE_URL + "data/";

async function json<T>(path: string): Promise<T> {
  const r = await fetch(base + path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export async function loadIndex(): Promise<{ file: string; generatedAt: string; beforeMd: number | null; untuned: boolean }[]> {
  return json("index.json");
}

/** The snapshot, its model, and the season as it stood when the snapshot was taken. */
export async function loadSnapshot(file: string): Promise<Loaded> {
  const [snap, model, season] = await Promise.all([
    json<Snapshot>("snapshots/" + file),
    json<ModelJson>("snapshots/" + file.replace(/\.json$/, ".model.json")),
    json<SeasonJson>("season.json"),
  ]);
  const done = new Set(snap.finished);
  season.fixtures = season.fixtures.map((f) =>
    done.has(f.id) ? f : { ...f, status: f.status === "FINISHED" ? "UPCOMING" : f.status, hg: null, ag: null },
  );
  return { snap, model, season, file };
}
