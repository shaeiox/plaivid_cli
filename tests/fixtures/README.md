# Synthetic parser fixtures

These files are synthetic fixtures shaped only from parser paths and repository documentation already present in this project. They are not captured PVM output, do not verify a supported PVM version, and must not be used as evidence of host/vendor behavior. Owner-provided, redacted target captures may be added later with provenance and authorization.

`nic-list.xml` is shaped like the `sbell network nic-list` output on the target host, with MAC addresses replaced by documentation-range placeholders. Device names and PVM NIC names are kept as observed.

`monitoring-metrics.xml` mirrors the structure of an authorized `sbell monitoring metrics` response (system_info, load_stats, process_stats, system_stats, temperature_stat_list, user_list, process_info_item). Values and the token-like text are synthetic; it is not a capture from a target host.

`sball-show.xml` is shaped like the `sball show` response (`node/resource_usage` with `release_info`, `cpus`, `system_information` and `root`). Node name and IP are documentation-range placeholders; version, CPU and memory values are kept as observed.
