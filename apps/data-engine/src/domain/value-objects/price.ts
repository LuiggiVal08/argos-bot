/**
 * Price in quote currency (e.g. USDT for BTC/USDT).
 *
 * Stored as bigint minor units (e.g. cents) to avoid float drift in
 * financial arithmetic. 1 BTC at $60_000.12345678 -> 6000012345678n
 * with `decimals = 8`.
 */
export class Price {
  private constructor(
    public readonly minor: bigint,
    public readonly decimals: number,
  ) {
    if (decimals < 0 || decimals > 18) {
      throw new Error(`Price: decimals out of range (0..18), got ${decimals}`)
    }
    if (!Number.isFinite(Number(minor))) {
      throw new Error(`Price: minor must be a bigint, got ${typeof minor}`)
    }
  }

  static ofMinor(minor: bigint, decimals = 8): Price {
    return new Price(minor, decimals)
  }

  /**
   * Parse a string like "60000.12345678" into a Price with the given
   * number of decimals (defaults to 8). Truncates excess fractional
   * digits, refuses negative or non-numeric input.
   */
  static parse(input: string | number, decimals = 8): Price {
    if (typeof input === "number") {
      if (!Number.isFinite(input) || input < 0) {
        throw new Error(`Price.parse: invalid number ${input}`)
      }
      input = input.toFixed(decimals)
    }
    const s = (input as string).trim()
    if (!/^\d+(\.\d+)?$/.test(s)) {
      throw new Error(`Price.parse: invalid string '${input}'`)
    }
    const [intPart, fracPartRaw = ""] = s.split(".")
    const fracPart = (fracPartRaw + "0".repeat(decimals)).slice(0, decimals)
    const minor = BigInt(intPart) * BigInt(10) ** BigInt(decimals) + BigInt(fracPart || "0")
    return new Price(minor, decimals)
  }

  toString(): string {
    const div = BigInt(10) ** BigInt(this.decimals)
    const int = this.minor / div
    const frac = this.minor % div
    return `${int.toString()}.${frac.toString().padStart(this.decimals, "0")}`
  }

  toNumber(): number {
    return Number(this.minor) / Number(BigInt(10) ** BigInt(this.decimals))
  }

  /** Serialize for transport (JSON-safe). */
  toJSON(): { minor: string; decimals: number } {
    return { minor: this.minor.toString(), decimals: this.decimals }
  }

  static fromJSON(raw: { minor: string; decimals: number }): Price {
    return new Price(BigInt(raw.minor), raw.decimals)
  }

  equals(other: Price | null | undefined): boolean {
    return (
      !!other &&
      other.minor === this.minor &&
      other.decimals === this.decimals
    )
  }
}
