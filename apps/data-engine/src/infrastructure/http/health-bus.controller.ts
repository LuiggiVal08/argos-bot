import { Controller, Get } from "@nestjs/common"
import { BusHealthMonitor } from "../messaging/bus-health-monitor"
import { HEALTH_MONITOR } from "../config/tokens"
import { Inject } from "@nestjs/common"

@Controller("health/bus")
export class HealthControllerBus {
  constructor(
    @Inject(HEALTH_MONITOR) private readonly monitor: BusHealthMonitor,
  ) {}

  @Get()
  health(): { healthy: boolean } {
    return { healthy: this.monitor.isHealthy() }
  }
}
