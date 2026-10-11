export type ClubId = string;

export interface Fixture {
  id: string;
  md: number;
  home: ClubId;
  away: ClubId;
  kickoff: string;
}

export interface Result {
  id: string;
  hg: number;
  ag: number;
}

export interface ClubParams {
  name: string;
  country: string;
  att: number;
  def: number;
  sd_att: number;
  sd_def: number;
}

export interface ModelJson {
  version: number;
  cutoff: string;
  input_hash: string;
  hyper: Record<string, number>;
  rho: number;
  mu_eur: number;
  h_eur: number;
  clubs: Record<ClubId, ClubParams>;
}

export interface SeasonFixture extends Fixture {
  status: string;
  hg: number | null;
  ag: number | null;
}

export interface SeasonJson {
  seasonYear: number;
  clubs: Record<ClubId, { name: string; country: string }>;
  fixtures: SeasonFixture[];
}

export interface TableRow {
  club: ClubId;
  played: number;
  w: number;
  d: number;
  l: number;
  gf: number;
  ga: number;
  gd: number;
  pts: number;
  awayGf: number;
  awayW: number;
  oppPts: number;
  oppGd: number;
  oppGf: number;
}
