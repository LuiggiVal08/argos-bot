const log = (m: string): void => {
  // eslint-disable-next-line no-console
  console.log(m)
}

/**
 * Sends a notification to a Telegram chat via the Bot API.
 * Fire-and-forget: failures are logged but not thrown.
 */
export async function sendTelegram(
  title: string,
  message: string,
  symbol?: string,
): Promise<void> {
  const token = process.env.TELEGRAM_BOT_TOKEN
  const chatId = process.env.TELEGRAM_CHAT_ID
  if (!token || !chatId) return

  const text = `<b>${title}</b>\n${message}${symbol ? `\n<b>Symbol</b>: ${symbol}` : ""}`

  try {
    const res = await fetch(
      `https://api.telegram.org/bot${token}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          parse_mode: "HTML",
          disable_web_page_preview: true,
        }),
      },
    )
    if (!res.ok) {
      const body = await res.text()
      log(`[telegram] API error ${res.status}: ${body.slice(0, 200)}`)
    }
  } catch (err) {
    log(`[telegram] send failed: ${String(err)}`)
  }
}
