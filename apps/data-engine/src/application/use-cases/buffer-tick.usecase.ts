import { Tick } from "../../domain/entities/tick"
import { TickBuffer } from "../ports/tick-buffer.port"

/**
 * Buffer a tick explicitly. Used as a fallback when the broker is
 * known to be down, or when the IngestTickUseCase already caught
 * a publish error and we want to retry the buffer step.
 */
export class BufferTickUseCase {
  constructor(private readonly buffer: TickBuffer) {}

  async execute(tick: Tick): Promise<void> {
    await this.buffer.push(tick)
  }
}
