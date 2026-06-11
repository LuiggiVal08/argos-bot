import * as fs from "fs"
import * as path from "path"
import { HistoricalEvent } from "../../domain/entities/historical-event"
import { EventStore } from "../../application/ports/event-store.port"

export interface FileEventStoreOptions {
  baseDir: string
}

export class FileEventStore implements EventStore {
  private readonly baseDir: string
  private writers = new Map<string, fs.WriteStream>()

  constructor(opts: FileEventStoreOptions) {
    this.baseDir = opts.baseDir
    fs.mkdirSync(this.baseDir, { recursive: true })
  }

  async store(event: HistoricalEvent): Promise<void> {
    const file = this.fileFor(event)
    let stream = this.writers.get(file)
    if (!stream) {
      fs.mkdirSync(path.dirname(file), { recursive: true })
      stream = fs.createWriteStream(file, { flags: "a" })
      this.writers.set(file, stream)
    }
    const line = JSON.stringify(event) + "\n"
    stream.write(line)
  }

  async *read(
    kind: HistoricalEvent["kind"],
    fromTs: number,
    toTs: number,
  ): AsyncIterable<HistoricalEvent> {
    const startDay = this.day(fromTs)
    const endDay = this.day(toTs)
    const current = new Date(startDay)
    const end = new Date(endDay)
    while (current <= end) {
      const dayStr = current.toISOString().slice(0, 10)
      const file = path.join(this.baseDir, kind, `${dayStr}.jsonl`)
      if (fs.existsSync(file)) {
        const content = fs.readFileSync(file, "utf-8")
        for (const line of content.split("\n").filter(Boolean)) {
          const event = JSON.parse(line) as HistoricalEvent
          if (
            event.kind === kind &&
            "ts" in event.data &&
            typeof event.data.ts === "number" &&
            event.data.ts >= fromTs &&
            event.data.ts <= toTs
          ) {
            yield event
          }
        }
      }
      current.setDate(current.getDate() + 1)
    }
  }

  private fileFor(event: HistoricalEvent): string {
    let ts = Date.now()
    if (event.kind === "tick") {
      ts = event.data.ts
    } else if (event.kind === "candle") {
      ts = event.data.openTs
    } else if (event.kind === "feature") {
      ts = event.data.timestamp
    }
    const dayStr = new Date(ts).toISOString().slice(0, 10)
    return path.join(this.baseDir, event.kind, `${dayStr}.jsonl`)
  }

  private day(ts: number): Date {
    const d = new Date(ts)
    d.setHours(0, 0, 0, 0)
    return d
  }
}
