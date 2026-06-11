/**
 * DI tokens. Using symbols avoids stringly-typed bindings and is
 * tree-shakable / rename-safe.
 */
export const BUS = Symbol("BUS")
export const EXCHANGE_GATEWAY = Symbol("EXCHANGE_GATEWAY")
export const TICK_BUFFER = Symbol("TICK_BUFFER")
export const HEALTH_MONITOR = Symbol("HEALTH_MONITOR")
export const STREAM_NAME = Symbol("STREAM_NAME")
