import type { ModelJson, SeasonJson, SeasonOut } from "@cutline/sim";

export interface Snapshot extends SeasonOut {
  generatedAt: string;
  seasonYear: number;
  beforeMd: number | null;
  modelCutoff: string;
  inputHash: string;
  untuned: boolean;
  notes: string[];
  finished: string[];
}

export interface Loaded {
  snap: Snapshot;
  model: ModelJson;
  season: SeasonJson; // statuses reset to the snapshot's finished set
  file: string;
}
