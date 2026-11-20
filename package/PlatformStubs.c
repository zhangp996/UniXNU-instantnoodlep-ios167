// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board bring-up stubs for the weak platform observers the storage/CPU drivers import.
// The kernel link refuses even weak undefined externals, so these provide truthful
// no-op definitions until the board services exist (fuxi/nx769j bring-up pattern):
//   boot_progress_poll      - passive boot-progress observer; no reporter yet.
//   arm64_platform_sleep_hook - ArmCpu assigns its own handler at runtime when sleep=1;
//                               start NULL so no platform sleep is attempted before then.
typedef int boolean_t;

void (*arm64_platform_sleep_hook)(boolean_t boot_cpu) = 0;

void
boot_progress_poll(void)
{
}
