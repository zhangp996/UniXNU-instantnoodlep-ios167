// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board verified-root boot probe (header-only policies). bsd_init calls this only when
// the offline-owner-root-check boot argument is set (offline-owner-root-crypto-probe
// patch). It authenticates every embedded header-only owner policy with the real kit
// crypto, the header-only analogue of the reference full-manifest instrument. The 4 KiB
// block tables are not here; they live in userdata and NativeUfs checks them per read.
#include "verified_root.h"
#include <libkern/libkern.h>

// Layout of drivers/VirtioMmioBlock/VerifiedBlockPolicy.h (that header is C++ only).
struct NativeVerifiedBlockPolicy {
	const uint8_t *manifest;
	uint64_t manifestBytes;
};
extern const struct NativeVerifiedBlockPolicy verified_root_policies[];
extern const uint64_t verified_root_policy_count;
extern const struct vr_crypto vr_xnu_crypto;
extern const uint8_t verified_root_key[];

volatile uint32_t native_verified_root_status = 0;
volatile uint32_t native_verified_root_policies_ok = 0;

void
native_verified_root_probe(void)
{
	uint32_t ok = 0;
	for (uint64_t i = 0; i < verified_root_policy_count; ++i) {
		const struct NativeVerifiedBlockPolicy *policy = &verified_root_policies[i];
		struct vr_view view;
		if (policy->manifest && policy->manifestBytes == VR_HEADER_BYTES + VR_SIGNATURE_BYTES &&
		    vr_open_header(policy->manifest, policy->manifestBytes, verified_root_key, 1,
		                   &vr_xnu_crypto, &view) == VR_OK) {
			ok++;
		}
	}
	native_verified_root_policies_ok = ok;
	native_verified_root_status = (ok > 0 && ok == verified_root_policy_count) ? 1 : 0;
}
