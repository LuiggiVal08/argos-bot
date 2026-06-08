import { Tick } from "../../domain/entities/tick"

/**
 * In-memory fallback buffer for ticks.
 *
 * Used in the sad path (spec §5 Historia 1): if the broker is
 * unavailable, ticks are pushed here so they are not lost.
 *
 * The buffer is bounded (max capacity enforced by the implementation).
 * When full, oldest ticks are dropped (FIFO eviction).
 *
 * Adapter-agnostic. The implementation decides whether to use
 * an array, a circular buffer, a queue, etc.
 */
export interface TickBuffer {
  push(tick: Tick): Promise<void>
  size(): number
  capacity(): number
  /**
   * Drain all buffered ticks (oldest first) and return them.
   * The buffer is empty after this call.
   */
  drain(): Promise<Tick[]>
}
