// SPDX-License-Identifier: BSD-2-Clause-Patent
// SM8250 (kona) GCC registers used by UFS, transcribed as facts from the public
// Linux gcc-sm8250.c clock driver and the IN2020 stock base device tree
// (inputs/board/stock-base.dts). No write is performed by NativeUfs yet.
//
// Device-owned adaptation of the ShengUfs component (official UniXNU/ShengUfs
// @f020bd6, BSD-2-Clause, copyright blu-sharky): the SM8550 constants are
// replaced by the kona facts below; source filenames and the NativeUfs runtime
// class are preserved per the component catalog.
#ifndef NATIVE_UFS_GCC_UFS_H
#define NATIVE_UFS_GCC_UFS_H

// Physical windows from the IN2020 stock base DT (clock-controller@100000,
// ufshc@1d84000 reg 0x1d84000/0x3000 + ufs_ice 0x1d90000/0x8000).
#define GCC_BASE                      0x00100000ULL
#define UFS_HC_BASE                   0x01d84000ULL
#define UFS_HC_SIZE                   0x3000ULL

// gcc-sm8250.c: ufs_phy_gdsc.gdscr = 0x77004. kona has no separate UFS mem-phy
// GDSC (only ufs_phy_gdsc and ufs_card_gdsc), unlike SM8550's 0x9e000 block.
#define GCC_UFS_PHY_GDSCR             0x77004
#define GCC_UFS_MEM_PHY_GDSCR         0x9e000
#define GCC_UFS_MEM_PHY_GDSCR_PRESENT 0

// gcc-sm8250.c clk_branch enable_reg values (SM8550 sits 8 bytes higher).
#define GCC_UFS_PHY_AXI_ENABLE        0x77010
#define GCC_UFS_PHY_AHB_ENABLE        0x77018
#define GCC_UFS_PHY_TX_SYMBOL0_ENABLE 0x7701c
#define GCC_UFS_PHY_RX_SYMBOL0_ENABLE 0x77020
#define GCC_UFS_PHY_UNIPRO_CORE_ENABLE 0x7705c
#define GCC_UFS_PHY_ICE_CORE_ENABLE   0x77064
// kona gcc has no ufs_phy_aux branch (only ufs_card_phy_aux_clk_src); the AUX
// read is skipped and reported as 0.
#define GCC_UFS_PHY_PHY_AUX_ENABLE    0x770b0
#define GCC_UFS_PHY_PHY_AUX_PRESENT   0
#define GCC_UFS_PHY_RX_SYMBOL1_ENABLE 0x770b8
// bus_aggr_clk in the stock DT: gcc_aggre_ufs_phy_axi_clk, enable 0x770cc, HW clock gating bit1
#define GCC_AGGRE_UFS_PHY_AXI_ENABLE  0x770cc

#define GCC_UFS_BRANCH_ENABLE_BIT     0x1U

// Mainline sm8250.dtsi ufshc: iommus = <&apps_smmu 0x0e0 0>, <&apps_smmu 0x4e0 0>
// (anoc_1 / anoc_2 TBU paths of the same master). Both streams need the bypass.
// The stock node carries no iommus property; the ids come from mainline SoC dtsi.
#define UFS_SMMU_STREAM_PRIMARY       0x0e0
#define UFS_SMMU_STREAM_SECONDARY     0x4e0

// gcc_ufs_phy_ahb_clk and gcc_aggre_ufs_phy_axi_clk set hwcg_bit=1 in gcc-sm8250.c,
// so CLK_OFF=1 on an idle branch is normal; enable bits, not CLK_OFF, gate the probe.
// The reset and RPMh/TCSR/QMP-PHY programming are not represented here: their
// semantics are not qualified and NativeUfs must not write them speculatively.
#endif