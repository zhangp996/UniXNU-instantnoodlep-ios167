# 移植状态 — iOS 16.7.16 (20H392) / OnePlus 8 Pro IN2020

> 记录时间 2026-11-20。按官方文档 https://unixnu.com/zh/porting/ 的八个步骤推进，当前完成到第 4 步
> （解析并检查构建配置），第 5～7 步被四个硬门槛挡住。本文只记录实测事实与命令，不引用其他分支的产物。

## 1. 设备实测（fastboot）

| 项 | 值 | 来源 |
| --- | --- | --- |
| 序列号 | `fa8620b3` | `fastboot devices` |
| product / variant | `kona` / `SM8 UFS` | `fastboot getvar all` |
| 解锁 / 当前槽 | `unlocked:yes` / `a`，b 槽 unbootable | 同上 |
| 分区特征 | `op1`(0x12C00000)、`op2`(0x10000000)、`super`(0x380000000)、`userdata` f2fs | 同上 |
| 机型 | OnePlus 8 Pro（IN2020）：国内包 `IN2020domestic_11_13.1.0.185CN01` 与之匹配 | 本地原厂包 |

硬件参数取自原厂 `boot.img`/`dtbo.img`（`inputs/boot`、`inputs/dtbo`、`inputs/dts`）：
boot 头 v2（kernel 0x8000 / ramdisk 0x01000000 / tags 0x100，页 4096）；dtbo 19 个 overlay，
其中 5 个带 `s6sy791` 触控（变体 19065/19811/19805/20809…），面板为 1440×3168 DSC 命令屏。

## 2. 已完成的适配层

| 文件 | 内容 |
| --- | --- |
| `board.toml` | board/soc_source/kit/os_profile；组件 8 个；defconfig、DTS、firmware、bootimg、payload、package |
| `feeds.toml` + `local.toml` | SoC 固定到 `3481a8b`，本地用同级 `UniXNU-sm8250-common` 检出 |
| `configs/instantnoodlep_defconfig` | 首启配置：DT 平台 + ArmCpu + prelinked crypto；UFS/GPU 关闭并写明原因 |
| `dts/instantnoodlep.dts` | 包含 `sm8250.dtsi`；DRAM 0x80000000 + 8 GiB；UFS/PHY 显式 disabled |
| `patches/xnu/series` | 空，注释说明设备层暂无补丁 |
| `porting.toml` | 13 个区域，`porting-record.py check` 通过 |
| `profiles/os/ios-16.7.16-20H392/` | 本机实测常量（见下） |

### OS profile 实测（本机从 IPSW 直接测量）

| 项 | 值 | 方法 |
| --- | --- | --- |
| 镜像 | `iPhone10,3,iPhone10,6_16.7.16_20H392_Restore.ipsw`（6,171,035,648 B） | 本地文件 |
| 身份 | 16.7.16 / 20H392 / `d221ap` / ApBoardID 0x0E / ApChipID 0x8015 | BuildManifest.plist |
| kernelcache 成员 sha256 | `2d6a13d040aaf87c…` | zip 成员 |
| arm64 切片 sha256 / 大小 | `2ec297bac95bcba0…` / 50,937,856 B | IMG4→IM4P(krnl)→LZFSE→fat 切片 |
| 内核版本串 | `xnu-8796.142.1.703.8~1/RELEASE_ARM64_T8015`，Darwin 22.6.0 | 同上 |
| 源码基线 | `xnu-8796.141.3` = `1b191cb5…` | GitHub API 解引用 tag |
| prelink roots | 31 个 kext 全部在切片中命中 | 逐标识串检索 |
| StaticTrustCache | `63e01c03b31e1532…` | zip 成员 |

## 3. 四个硬门槛（按优先级）

1. **xnu-8796 补丁系列**：`profiles/arch/arm64/patches/xnu/series` 的 56 个补丁全部针对
   `xnu-10063`（iPadOS 17）。对 8796 直接 `git apply` 会在第一批 hunk 失败。需要逐条回植，
   产出本 profile 的 `patches/xnu/series`。
2. **kona UFS 存储组件**：`components.toml` 只有 `ShengUfs`（SM8750 范围），
   `UniXNU-sm8250-common` 的 `kits/` 为空。没有存储驱动 → 根卷/Data 卷无法挂载 → launchd 起不来。
   必须先写 kona UFS 组件（参照 UFS 指南），否则只能停在 RamBlock 首启。
3. **Mu-Silicium 固件包**：上游没有 `uefi-instantnoodlep`。`board.toml [firmware]` 的
   dsc/fd 路径是待建占位；固件需要 display/UFS/USB 的 UEFI 驱动，否则连菜单都进不去。
4. **构建主机**：内核步骤官方只支持 macOS/Linux（Windows 无法执行）。Data 种子需要 macOS
   `hdiutil`。可选路径：Linux 主机 + `scripts/linux/setup-toolchain.py`，或 fork 后跑
   `.github/workflows/package.yml` 的 macOS runner。

## 4. 复现命令

```sh
cd UniXNU
./unixnu defconfig instantnoodlep_defconfig -D ../UniXNU-instantnoodlep
./unixnu status --json -D ../UniXNU-instantnoodlep     # 已通过
./unixnu tree -D ../UniXNU-instantnoodlep              # 需要先 fetch 源码
python3 scripts/porting-record.py check --device ../UniXNU-instantnoodlep   # 13 areas
```

## 5. 仍待测量

- `[root] os_volume_uuid`：20H392 的 OS 盘是 UDIF 容器，需先走 chunk 还原再读 APFS
  `nx_superblock` 的卷 UUID（当前 `REQUIRED_OS_VOLUME_UUID`）。
- `[kernel.prelink] early_security_init`：需要在本 kernelcache 里测未滑动 AMFI 地址；
  未测前 emit_prelink 跳过该钩子。
- DRAM 实际容量（8 GiB 是 SKU 标称值，需在整机上确认）。
- `[ipsw.sha256]` 里两个 `.dmg` 与 DeviceTree 成员的 pin。

## 6. 2026-11-20 第二段：D → C

**D（Linux 构建主机）**
- WSL Ubuntu 22.04：`scripts/linux/setup-toolchain.py` 安装完成（host LLVM 14 + cctools ld64 + iig，
  lzfse 在 `/opt/unixnu-linux/bin`）；`python3.12` 已装（unixnu 要求 ≥3.11）。
- `unixnu fetch` 完成，源码固定写入 `unixnu.lock`；输出树在 `/root/uxout`（ext4，避免 DrvFs 拖慢编译）。
- `unixnu tree` 组装成功：`/root/uxout/instantnoodlep/ios-16.7.16-20H392/instantnoodlep/tree`。
- 内核构建已在 Linux 主机上发起，预计停在 8796 补丁应用（见门槛 1）。

**C（固件）**
- 结论：没有可直接用的 IN2020 Mu-Silicium 底座。
  - `kebab`（8T，SM8250）按你的判断弃用，且它的内存图和 FD 窗口与本板不同。
  - 社区 `musabcel/edk2-instantnoodlep`（F11）确实按 IN2020 命名，但：FDF 写 `0xD0000000/0x200000`，
    而 Mu-Silicium kona 窗口是 `0x9FC00000/0x300000`；帧缓冲写 1080x2400（8 Pro 实为 1440x3168）；
    自带的 `instantnoodlep.dtb` 是 `kona MTP dvt/mp 19811` 参考树，不是 OnePlus 树。
- 已建 `src/uefi-instantnoodlep`（overlay 结构 + DSC + Resources 配置 + sync 脚本 + FACTS 文档），
  三个未知量列在 `docs/FACTS.md`：FD 载入窗口、面板时序/DSC、固件 DTB。

**下一步需要你配合的一件事**：让手机进一次 Android（或 TWRP），我抓 `/proc/device-tree` 与
`/proc/iomem`，一次把上面三个量和板级 DTS 全部落定。没有这一步，D 能跑完但 C 只能停在骨架。

## 7. 2026-11-20 第三段：原厂固件包 + C 落地

**从 `D:\新建文件夹` 取数据（只拿不参考）**：拿到本机验证过的固件包与原厂设备树，C 的三个未知量全部解出：
- **FD 窗口 = 0x9F000000**（固件 config + MemoryMapLib 一致；`uefi_sec.mbn` 亦引用此址）。
  XBL 自身的 0xD0000000 是 DDR 区，正是社区 F11 误用的地址——弃用 F11/kebab 有据。
- **面板 = 1440×3168 @60/120Hz**（DSC FB PCD + 固件 DTB `panel-width 0x5a0 / height 0xc60`）。
- **固件 DTB = 真机 OnePlus 19805 树**（939,951 B，sha256 `f7fa0c06…`），非 F11 的参考 MTP 树。
- 完整 reserved-memory 与原厂 base DT 一致；94 个 IN2020 专用 XBL DXE 驱动已取用。
- 唯一构建期核对：验证 boot-menu 的 FD 二进制是 4 MiB，源 config/内存图是 3 MiB 自洽布局
  （栈 0x9F3F0000 与 3 MiB 不重叠）。先按 3 MiB 编，FV 放不下再升 4 MiB 并把栈移到 ≥0x9F400000。

**从原厂包 `..._解包` 取用**（inputs/stock）：abl.elf、xbl_ddr5/xbl_config、uefi_sec.mbn、devcfg.mbn、
gpt_main0.bin、splash.img、BTFM.bin。GPT 给出 **userdata first_lba 4133800**（末分区自动扩展），
结合 fastboot 尺寸 0x1928453000 算得 last_lba 30513146，已填入 board.toml [userdata]。
super.img（8 GiB）含 vendor 的 a650/s6sy791/UFS 固件，留待存储/GPU/输入适配时 lpunpack 提取。

**C 进展**：overlay 已合并进 Mu-Silicium 底座（/root/mu-silicium），board.toml [firmware]
packages/submodules/patches 补全（MuPatches 4 个，AsmMacroLib 已上游化），[bootimg.image] 对齐
验证值（base 0 / page 4096 / tags 0x100）。固件构建已发起（初始化 Mu 子模块中）。
