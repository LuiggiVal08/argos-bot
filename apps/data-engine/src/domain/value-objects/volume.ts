export class Volume {
  private constructor(public readonly minor: bigint, public readonly decimals: number) {
    if (decimals < 0 || decimals > 18) {
      throw new Error(`Volume: decimals out of range (0..18), got ${decimals}`)
    }
  }

  static zero(decimals = 8): Volume {
    return new Volume(0n, decimals)
  }

  static ofMinor(minor: bigint, decimals = 8): Volume {
    return new Volume(minor, decimals)
  }

  add(other: Volume): Volume {
    const d = Math.max(this.decimals, other.decimals)
    const a = this.scaleTo(d)
    const b = other.scaleTo(d)
    return new Volume(a.minor + b.minor, d)
  }

  equals(other: Volume | null | undefined): boolean {
    if (!other) return false
    const d = Math.max(this.decimals, other.decimals)
    return this.scaleTo(d).minor === other.scaleTo(d).minor
  }

  private scaleTo(targetDecimals: number): Volume {
    if (this.decimals === targetDecimals) return this
    const diff = targetDecimals - this.decimals
    if (diff > 0) return new Volume(this.minor * BigInt(10) ** BigInt(diff), targetDecimals)
    return new Volume(this.minor / BigInt(10) ** BigInt(-diff), targetDecimals)
  }

  toNumber(): number {
    return Number(this.minor) / Number(BigInt(10) ** BigInt(this.decimals))
  }

  toString(): string {
    const div = BigInt(10) ** BigInt(this.decimals)
    const int = this.minor / div
    const frac = this.minor % div
    return `${int.toString()}.${frac.toString().padStart(this.decimals, "0")}`
  }

  toJSON(): { minor: string; decimals: number } {
    return { minor: this.minor.toString(), decimals: this.decimals }
  }

  static fromJSON(raw: { minor: string; decimals: number }): Volume {
    return new Volume(BigInt(raw.minor), raw.decimals)
  }
}
