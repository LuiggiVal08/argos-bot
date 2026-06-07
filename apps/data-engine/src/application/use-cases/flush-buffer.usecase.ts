import { Tick } from "../../domain/entities/tick"
import { StreamName } from "../../domain/value-objects/stream-name"
import { MessageBus } from "../ports/message-bus.port"
import { TickBuffer } from "../ports/tick-buffer.port"

export interface FlushResult {
  drained: number
  published: number
  reBuffered: number
}

/**
 * Drain the in-memory buffer and re-publish each tick to the broker.
 *
 * Called when the HealthMonitor transitions from unhealthy to
 * healthy. If a publish fails mid-flush, the remaining ticks stay
 * in the buffer (no double-loss, no double-publish).
 */
export class FlushBufferUseCase {
  constructor(
    private readonly bus: MessageBus,
    private readonly buffer: TickBuffer,
    private readonly stream: StreamName,
  ) {}

  async execute(): Promise<FlushResult> {
    const ticks: Tick[] = await this.buffer.drain()
    let published = 0
    let reBuffered = 0
    let failed = false
    for (let i = 0; i < ticks.length; i++) {
      const t = ticks[i]!
      if (failed) {
        // Preserve the remaining ticks verbatim: push them back in
        // the original order. Buffer is FIFO so order matters.
        await this.buffer.push(t)
        reBuffered++
        continue
      }
      try {
        await this.bus.publish(this.stream, t)
        published++
      } catch {
        // Mark as failed; the current tick and all subsequent ones
        // must be re-buffered to avoid loss.
        failed = true
        await this.buffer.push(t)
        reBuffered++
      }
    }
    return { drained: ticks.length, published, reBuffered }
  }
}
