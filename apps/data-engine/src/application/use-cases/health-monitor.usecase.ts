import { ExchangeGateway } from "../ports/exchange-gateway.port"
import { HealthMonitor } from "../ports/health-monitor.port"
import { FlushBufferUseCase } from "./flush-buffer.usecase"

export interface HealthMonitorCallbacks {
  onUnhealthy: () => Promise<void> | void
  onHealthy: () => Promise<void> | void
}

/**
 * Wires the HealthMonitor port to the side effects required by the
 * spec sad path (spec §5 Historia 1):
 *
 *   - On unhealthy: NO-OP. IngestTickUseCase already routes failed
 *     publishes to the buffer. We just log the state change.
 *   - On unhealthy for `cutoffMs` (default 10s): close the WebSocket
 *     orderly (ExchangeGateway.close) to prevent candle history
 *     incoherence while the broker is down.
 *   - On healthy: trigger a FlushBufferUseCase to drain whatever
 *     was buffered during the outage.
 *
 * The cutoff is enforced via a timer started on the first unhealthy
 * probe and cleared on the first healthy probe.
 */
export class HealthMonitorUseCase {
  private unhealthySince: number | null = null
  private cutoffTimer: NodeJS.Timeout | null = null
  private hasFiredCutoff = false

  constructor(
    private readonly monitor: HealthMonitor,
    private readonly exchange: ExchangeGateway,
    private readonly flush: FlushBufferUseCase,
    private readonly opts: { cutoffMs: number; onLog: (msg: string) => void },
  ) {
    if (opts.cutoffMs <= 0) {
      throw new Error("HealthMonitorUseCase: cutoffMs must be > 0")
    }
  }

  /**
   * Poll-based controller. Call this from a setInterval in the
   * infrastructure layer. It is intentionally simple and dependency-
   * free so it can be tested without a real timer.
   */
  async tick(): Promise<void> {
    const healthy = this.monitor.isHealthy()
    if (healthy) {
      if (this.unhealthySince !== null) {
        this.opts.onLog(
          `[health] broker recovered after ${Date.now() - this.unhealthySince}ms — flushing buffer`,
        )
        this.unhealthySince = null
        this.hasFiredCutoff = false
        if (this.cutoffTimer) {
          clearTimeout(this.cutoffTimer)
          this.cutoffTimer = null
        }
        try {
          const res = await this.flush.execute()
          this.opts.onLog(
            `[health] flush: drained=${res.drained} published=${res.published} reBuffered=${res.reBuffered}`,
          )
        } catch (e) {
          this.opts.onLog(`[health] flush error: ${(e as Error).message}`)
        }
      }
      return
    }
    // Unhealthy.
    if (this.unhealthySince === null) {
      this.unhealthySince = Date.now()
      this.opts.onLog(
        `[health] broker unhealthy; cutoff in ${this.opts.cutoffMs}ms`,
      )
      this.cutoffTimer = setTimeout(() => {
        if (this.unhealthySince !== null && !this.hasFiredCutoff) {
          this.hasFiredCutoff = true
          this.opts.onLog(
            `[health] cutoff reached after ${this.opts.cutoffMs}ms — closing exchange WS`,
          )
          void this.exchange.close()
        }
      }, this.opts.cutoffMs)
    }
  }
}
