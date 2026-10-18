# CSIFormer Phase 16 — Dataset Quality & Integrity Verification Report

**Verification Status:** **PASS**  
**Audit Scope:** Physical ESP32-S3 Promiscuous CSI Dataset (`data/real_csi_dataset/`)  
**Total Declared Sessions:** 23  
**Total Parsed Frames:** 3212  
**Total Non-Overlapping Windows $[50, 56]$:** 49

---

## 1. Automated Integrity Checks Matrix

| Integrity Check Category | Verification Criteria | Measured Result | Status |
| :--- | :--- | :---: | :---: |
| **Session ID Uniqueness** | Zero duplicate session IDs in manifest | 0 duplicates | **PASS** |
| **File Persistence** | 100% of declared JSON & CSV files exist on disk | 0 missing | **PASS** |
| **Packet Count Consistency** | Manifest packet counts match file lengths | 0 mismatches | **PASS** |
| **Label Validity** | All labels within predefined HAR taxonomy | 0 invalid | **PASS** |
| **Class ID Mapping** | Class IDs strictly match model schema | 0 mismatches | **PASS** |
| **Signal Data Sanity** | Zero NaNs, Infs, or non-finite values in CSI | 0 non-finite | **PASS** |
| **Subcarrier Format** | Exactly 56 aligned HT20 active subcarriers | 0 malformed | **PASS** |
| **Session Split Isolation** | Zero session overlap between Train, Val, Test | 0 overlapping | **PASS** |
| **Window Duplication** | Zero identical window hashes across dataset | 0 duplicates | **PASS** |
| **Participant Leakage** | Subject isolation between Train and Test | ['Participant_02'] | **CAUTION (Seen-Subject)** |

---

## 2. Window Distribution Across Splits

| Activity Class | Model Class ID | Train Split Windows | Val Split Windows | Held-Out Test Windows | Total Windows |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **push_pull** | 0 | 5 | 2 | 2 | 9 |
| **clap** | 2 | 4 | 2 | 2 | 8 |
| **static** | 6 | 3 | 2 | 0 | 5 |
| **sit** | 8 | 5 | 2 | 3 | 10 |
| **fall** | 9 | 4 | 2 | 2 | 8 |
| **walk** | 11 | 5 | 2 | 2 | 9 |
| **Total** | -- | **26** | **12** | **11** | **49** |

---

## 3. Telemetry & Timing Anomalies

- **Total Timestamp Inversions Detected:** 0 (System clock strictly monotonic).
- **Cumulative Sequence Gaps (Lost Packets):** 0 frames lost over all sessions.
- **Average Hardware Frame Loss Rate:** 0.00%.

---

## 4. Scientific Recommendations for Dataset Expansion

1. **Address Participant Overlap:** ['Participant_02'] must be isolated in future collection phases so that test evaluation is strictly Leave-One-Subject-Out (LOSO).
2. **Expand Held-Out Fall Test Windows:** The current held-out test split contains only **2 fall windows**, which is insufficient for clinical confidence ($p = 0.90 \pm 0.10$ requires $N \ge 35$).
3. **Preserve Raw Subcarrier Storage:** All subsequent recordings must store both the raw un-interpolated 5-subcarrier measurements and the 56-subcarrier aligned representations.
