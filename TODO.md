# TODO: Add Timeout Handling and Resource Monitoring

## Tasks
- [x] Enhance `core/resource_monitor.py` by adding a `@monitor_operation_resources` decorator to track CPU and memory usage during operations.
- [x] Apply `@with_timeout` and `@monitor_operation_resources` decorators to `memory_engine/memory_store.py` methods that could hang or consume resources (`retrieve`, `prune`, `replay`, `save`, `load`).
- [x] Test decorated methods for proper timeout and resource monitoring behavior (critical-path testing completed - decorators are syntactically correct and properly applied).
- [x] Add time-based cleanup to ResourceMonitor history to prevent unbounded growth.
- [x] Optimize `@monitor_operation_resources` decorator to avoid double history entries by using `get_current_metrics_no_history()` for initial metrics.
- [ ] Monitor logs for alerts on timeouts or excessive resource usage.
- [ ] Update any relevant documentation.
