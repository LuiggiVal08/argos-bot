import { Controller, Get, Inject } from "@nestjs/common"
import { ConfigService } from "@nestjs/config"
import { BUS } from "../config/tokens"
import { RedisProtocolBus } from "../messaging/redis-protocol-bus"

@Controller("health")
export class HealthController {
  constructor(
    private readonly config: ConfigService,
    @Inject(BUS) private readonly bus: RedisProtocolBus,
  ) {}

  @Get()
  async health(): Promise<{
    status: "ok" | "degraded"
    mode: string
    broker: boolean
  }> {
    const brokerOk = await this.bus.ping()
    return {
      status: brokerOk ? "ok" : "degraded",
      mode: this.config.get<string>("ENVIRONMENT_MODE", "PAPER_TRADING"),
      broker: brokerOk,
    }
  }
}
