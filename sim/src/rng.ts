/** xoshiro128** seeded with splitmix32: fast in JS (32-bit words, no BigInt), deterministic per seed. */
export class Rng {
  private s0: number;
  private s1: number;
  private s2: number;
  private s3: number;

  constructor(seed: number) {
    let x = seed >>> 0;
    const split = () => {
      x = (x + 0x9e3779b9) >>> 0;
      let z = x;
      z = Math.imul(z ^ (z >>> 16), 0x85ebca6b);
      z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35);
      return (z ^ (z >>> 16)) >>> 0;
    };
    this.s0 = split();
    this.s1 = split();
    this.s2 = split();
    this.s3 = split();
  }

  /** Uniform in [0, 1). */
  next(): number {
    const r = Math.imul(rotl(Math.imul(this.s1, 5), 7), 9) >>> 0;
    const t = this.s1 << 9;
    this.s2 ^= this.s0;
    this.s3 ^= this.s1;
    this.s1 ^= this.s2;
    this.s0 ^= this.s3;
    this.s2 ^= t;
    this.s3 = rotl(this.s3, 11);
    return r / 4294967296;
  }

  /** Standard normal (Box–Muller). */
  normal(): number {
    let u = this.next();
    while (u === 0) u = this.next();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * this.next());
  }
}

function rotl(x: number, k: number): number {
  return (x << k) | (x >>> (32 - k));
}
