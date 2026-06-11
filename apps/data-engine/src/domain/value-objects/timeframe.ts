const UNIT_MS: Record<string, number> = { m: 60_000, h: 3_600_000 }

const ALLOWED: { value: number; unit: string }[] = [
  { value: 1, unit: "m" },
  { value: 5, unit: "m" },
  { value: 15, unit: "m" },
  { value: 1, unit: "h" },
]

export class Timeframe {
  private constructor(
    public readonly value: number,
    public readonly unit: "m" | "h",
  ) {}

  static get ONE_MIN(): Timeframe {
    return new Timeframe(1, "m")
  }
  static get FIVE_MIN(): Timeframe {
    return new Timeframe(5, "m")
  }
  static get FIFTEEN_MIN(): Timeframe {
    return new Timeframe(15, "m")
  }
  static get ONE_HOUR(): Timeframe {
    return new Timeframe(1, "h")
  }

  static ALL: Timeframe[] = [
    Timeframe.ONE_MIN,
    Timeframe.FIVE_MIN,
    Timeframe.FIFTEEN_MIN,
    Timeframe.ONE_HOUR,
  ]

  static parse(raw: string): Timeframe {
    const m = /^(\d+)([mh])$/.exec(raw.trim())
    if (!m) throw new Error(`Timeframe.parse: invalid format '${raw}'`)
    const value = Number(m[1])
    const unit = m[2] as "m" | "h"
    const ok = ALLOWED.some((a) => a.value === value && a.unit === unit)
    if (!ok) throw new Error(`Timeframe.parse: unsupported '${raw}'`)
    return new Timeframe(value, unit)
  }

  toMilliseconds(): number {
    return this.value * UNIT_MS[this.unit]
  }

  toString(): string {
    return `${this.value}${this.unit}`
  }

  equals(other: Timeframe | null | undefined): boolean {
    return !!other && other.value === this.value && other.unit === this.unit
  }
}
