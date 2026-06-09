const COLORS: Record<string, number> = {
  INFO: 0x00ff00,
  WARN: 0xffa500,
  CRITICAL: 0xff0000,
}

const log = (m: string): void => {
  // eslint-disable-next-line no-console
  console.log(m)
}

export interface DiscordPayload {
  event_type: string
  severity: string
  title: string
  message: string
  symbol?: string
  timestamp: string
}

/**
 * Sends a notification to a Discord channel via webhook URL.
 * Fire-and-forget: failures are logged but not thrown.
 */
export async function sendDiscord(payload: DiscordPayload): Promise<void> {
  const url = process.env.DISCORD_WEBHOOK_URL
  if (!url) return

  const embed: Record<string, unknown> = {
    title: payload.title,
    description: payload.message,
    color: COLORS[payload.severity] ?? 0x808080,
    timestamp: payload.timestamp,
  }
  if (payload.symbol) {
    embed.fields = [{ name: "Symbol", value: payload.symbol, inline: true }]
  }

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ embeds: [embed] }),
    })
    if (!res.ok && res.status !== 204) {
      const body = await res.text()
      log(`[discord] webhook error ${res.status}: ${body.slice(0, 200)}`)
    }
  } catch (err) {
    log(`[discord] send failed: ${String(err)}`)
  }
}
