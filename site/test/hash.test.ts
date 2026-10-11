import { describe, expect, test } from "vitest";
import { decodeForced, encodeForced } from "../src/hash.ts";

const ids = new Set(["2049556", "2049557", "2049558"]);

describe("forced-result hash", () => {
  test("round-trips three results", () => {
    const m = new Map([
      ["2049556", { id: "2049556", hg: 1, ag: 0 }],
      ["2049557", { id: "2049557", hg: 2, ag: 2 }],
      ["2049558", { id: "2049558", hg: 0, ag: 3 }],
    ]);
    const h = encodeForced(m);
    expect(h).toBe("#f=2049556:1-0,2049557:2-2,2049558:0-3");
    expect(decodeForced(h, ids)).toEqual(m);
  });

  test("drops an unknown fixture id and keeps the rest", () => {
    const got = decodeForced("#f=999:1-0,2049556:1-1", ids);
    expect([...got.keys()]).toEqual(["2049556"]);
  });

  test("drops a malformed score", () => {
    expect(decodeForced("#f=2049556:3-x,2049557:-1-0,2049558:2-1", ids).size).toBe(1);
  });

  test("empty or foreign hash gives an empty map", () => {
    expect(decodeForced("", ids).size).toBe(0);
    expect(decodeForced("#top", ids).size).toBe(0);
    expect(encodeForced(new Map())).toBe("");
  });
});
