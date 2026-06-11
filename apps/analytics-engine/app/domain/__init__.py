"""Domain value objects and entities for the analytics-engine.

Per AGENTS.md invariant #8: this layer must not import from application
or infrastructure. It is a pure-Python core that contains the trading
risk rules. Any I/O (CCXT, TA, broker) is wired through the application
layer's ports.
"""
