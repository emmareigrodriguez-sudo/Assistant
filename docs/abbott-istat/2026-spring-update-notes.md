# Abbott i-STAT — Spring 2026 Updates

## Key Dates & Actions

| Event | Date | Notes |
|---|---|---|
| **i-STAT 1 Global SW Update released** | 14 April 2026 | Email notification sent to customers. Roche is a customer. |
| **Current SW (i-STAT 1) expires** | June 2026 | Must update before expiry |
| **New SW (i-STAT 1) expires** | Early December 2026 | Intentionally before Christmas to avoid holiday conflicts |
| **i-STAT Alinity OSi24 release date** | 27 April 2026 | Email notification to APOC commercial and customers |
| **Current OSi23 software expires** | 15 July 2026 (8:00am local) | Must update before expiry |
| **New OSi24 software expires** | 13 January 2027 (8:00am local) | |
| **Operator certification date** | Impacted — see fixes below | Conflicting notifications and premature lockout fixed in this release |

---

## i-STAT Alinity Product Update (OSi24)

**Description:** Mandatory twice-a-year i-STAT Alinity OSi software release necessary to update standardization values to maintain long-term consistency of performance and enable new features.

- **New version:** OSi24
- **Software expires:** 13-Jan-2027 (at 8:00am local)
- **Release Date:** Apr 27, 2026
- **Email notification:** Software release to APOC commercial and customers (Coming Soon → Now Available → Expiring Soon)
- **OSi23 software expires:** 15-Jul-2026 (at 8:00am local)
- **Available at:** [www.globalpointofcare.abbott](https://www.globalpointofcare.abbott)

---

## i-STAT Alinity OSi — Software Updates and Enhancements

1. **Improved heartbeat reliability** — Updated user module heartbeat reliability and optimized system startup performance which strengthens system stability.

2. **Large dataset performance** — Enhanced patient lists, operator lists, and cartridge lists logic to significantly reduce processing time for large datasets.

3. **New QC failure code** — Enhanced to include a new quality check failure code (QCF 131-01-5.1.29) to better detect underfill events when running an hs-TnI cartridge.

4. **Operator certification notification fix** — Resolved an issue that caused conflicting operator certification expiration notifications. The enhancement prevents scenarios where users could see both "about to expire" and "expired" alerts on the same expiration date.

5. **Premature operator lockout fix** — Fixed premature operator certification expiration when dates transmitted from the data manager have missing timestamp fields which caused unexpected operator lockout.

6. **Printer module fix** — Resolved an issue where the i-STAT Alinity printer module generated a fatal error intermittently when communication could not be established due to the printer being off or the instrument being incorrectly aligned with the printer IR port.

---

## i-STAT 1 — End-of-Support Reminders (repeat reminder)

### Microsoft Windows Server®

Many Abbott and partner products are compatible with and run on various operating systems and browsers. From time-to-time those systems come to the end of their useful life and are retired.

- **Microsoft Windows Server® 2022** — End of 'Mainstream' Support date of **October 13, 2026**. Extended Support will still be available through **October 14, 2031**.

- **Microsoft Windows Server® 2016** — End of 'Extended' Support date of **January 12, 2027**. This will be the final Microsoft support date for Windows Server 2016.

**Action required:** Coordinate with your IT team and Data Management vendor to arrange a transition to a supported operating system prior to the end of support for your systems supporting i-STAT.

**User documentation:** [https://www.globalpointofcare.abbott/ww/en/support.html](https://www.globalpointofcare.abbott/ww/en/support.html)

For assistance with transitioning any of the listed components contact your local i-STAT representative.

---

## Impact on navify POC Operations (POCM)

### What POCM needs to consider:

1. **OSi24 compatibility** — Verify that navify POC Operations 3.4/3.5 is compatible with the new OSi24 firmware on i-STAT Alinity devices.

2. **Operator certification fix (#4, #5)** — The fixes for conflicting certification notifications and premature lockout may affect how POCM handles operator certification data received from i-STAT Alinity. Verify that the LMS import and operator certification workflows still work correctly.

3. **New QCF code (#3)** — The new quality check failure code QCF 131-01-5.1.29 for hs-TnI underfill events needs to be recognized by POCM's QC module. Check if the code is already in the QC failure code definitions or needs to be added.

4. **Windows Server 2016 EOL (Jan 2027)** — Customers running POCM on Windows Server 2016 need to plan migration. This aligns with the nPOCOs 3.5.0 release timeline.

5. **Customer communication** — Affiliates need to be informed about the SW update timeline and expiry dates to coordinate with their i-STAT fleet updates.

---

*Source: i-STAT Spring 2026 GSR Review v1 — For internal use only, not for customer distribution*
*Recorded: April 2026*
