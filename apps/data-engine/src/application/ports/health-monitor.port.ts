/**
 * Health monitor port.
 *
 * Periodically probes the broker. When the broker has been
 * unreachable for `cutoffMs` consecutive milliseconds, fires
 * `onUnhealthy` exactly once (until a healthy probe resets it).
 *
 * When the broker is healthy again, fires `onHealthy` exactly once.
 *
 * Implementation-agnostic. The adapter decides how to probe
 * (TCP ping, RESP PING, HTTP /health, etc.).
 */
export interface HealthMonitor {
  start(): void
  stop(): Promise<void>
  /** Synchronous snapshot of current state. */
  isHealthy(): boolean
}
