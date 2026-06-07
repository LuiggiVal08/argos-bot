"""Infrastructure layer: concrete adapters for the application ports.

Per AGENTS.md invariant #11, third-party libraries that have nothing
to do with the domain (ta, ccxt, redis client wrappers, etc.) live
ONLY here. The application and domain layers stay pure.
"""
