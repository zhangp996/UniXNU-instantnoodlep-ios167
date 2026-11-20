# UniXNU-instantnoodlep — iOS 16.7.16 (20H392) on OnePlus 8 Pro (IN2020)

Format 2 device repository for **OnePlus 8 Pro (IN2020, kona, SM8250)** targeting
**iOS 16.7.16 (20H392), iPhone X (iPhone10,6 / D221AP) arm64** identity.

- SoC support: [zhangp996/UniXNU-sm8250-common](https://github.com/zhangp996/UniXNU-sm8250-common) @ `3481a8b`
- OS profile: `profiles/os/ios-16.7.16-20H392` (constants measured from the restore image)
- Kernel source: `xnu-8796.141.3` (public tag closest to the 8796.142 kernel in the restore image)

## State

The configuration layer resolves and the record passes its checker. **It does not boot yet.**
Read [docs/PORT-STATUS.md](docs/PORT-STATUS.md) for the four open gates (8796 patch series,
kona UFS component, Mu-Silicium firmware package, Linux/macOS build host) and the exact
commands.

## Commands

```sh
# from the UniXNU checkout
./unixnu defconfig instantnoodlep_defconfig -D ../UniXNU-instantnoodlep
./unixnu status --json -D ../UniXNU-instantnoodlep
./unixnu tree -D ../UniXNU-instantnoodlep
python3 scripts/porting-record.py check --device ../UniXNU-instantnoodlep
```

Build inputs that are not in any repository: the restore image (`--ipsw`), the Mu-Silicium
firmware checkout (`--uefi`), and the platform seed (`--unique-chip-id`).
