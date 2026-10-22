# Changes

## 0.19.0-preview.1

- Isolate live sensor delivery from diagnostic-file export failures. Permission
  errors or a full disk must not stop healthy readings from reaching the interface.
- Preserve network/disk API failure reasons and numeric error codes instead of
  reporting every unavailable reading as a counter warm-up.
- Reuse unchanged HWiNFO registry exports after verifying access and their original
  FILETIME; do not repeatedly enumerate and parse every channel at fast sampling rates.
- Prepare a clean, allowlisted source snapshot with SHA-256 file integrity checks;
  omit old application releases, local profiles, logs and private QA records.
- Offer original new application versions under PolyForm Noncommercial 1.0.0;
  retain third-party and earlier MIT rights explicitly.
- Document a safe isolated test workflow and the limits of sensor and glass checks.

This is a development preview. An offscreen layout check is not proof of Windows
composition quality or universal hardware compatibility.
